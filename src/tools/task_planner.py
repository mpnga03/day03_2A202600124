from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

from src.core.gemini_provider import GeminiProvider

def _parse_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError("exam_date/start_date must be in dd/mm/yyyy or yyyy-mm-dd format")


def _date_range(start: date, end: date) -> List[date]:
    days = (end - start).days
    if days < 0:
        return []
    return [start + timedelta(days=i) for i in range(days + 1)]


def _extract_first_json_object(text: str) -> Dict[str, Any]:
    """
    Extract first JSON object from model output.
    Handles cases where model adds extra text around JSON.
    """
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model output")
    return json.loads(match.group(0))


def _build_planner_prompt(
    start_iso: str,
    exam_iso: str,
    total_days: int,
    hours_per_day: float,
    final_practice_days: int,
    focus: str,
) -> str:
    return f"""
You are an ML study planner assistant.
Output must be valid JSON only.
Do not write markdown.
Do not write explanations.
Output must start with '{{' and end with '}}'.

Constraints:
- start_date: {start_iso}
- exam_date: {exam_iso}
- total_days: {total_days}
- hours_per_day: {hours_per_day}
- focus: {focus}
- Reserve exactly {min(final_practice_days, total_days)} final days for practical exam preparation.
- Every day must have total duration exactly {hours_per_day} hours.
- Emphasize basic ML: preprocessing, supervised learning, unsupervised learning, practice exams.

Output schema:
{{
  "phases": [
    {{"phase":"foundation","days":int,"topics":[str,...]}},
    {{"phase":"core_models","days":int,"topics":[str,...]}},
    {{"phase":"final_practice","days":int,"topics":[str,...]}}
  ],
  "daily_plan": [
    {{
      "day_index": int,
      "phase": str,
      "main_topic": str,
      "tasks": [str, str, str]
    }}
  ]
}}
"""


def _build_repair_prompt(
    broken_text: str,
    error_msg: str,
    total_days: int,
    hours_per_day: float,
) -> str:
    return f"""
You are a JSON repair assistant.
Fix the following planner output into valid JSON only.
No markdown. No explanations.
Output must start with '{{' and end with '}}'.

Validation error:
{error_msg}

Hard constraints:
- daily_plan must have exactly {total_days} items
- day_index must be 1..{total_days}
- each item has: day_index, phase, main_topic, tasks
- tasks must be a non-empty list of strings
- schedule is {hours_per_day} hours/day

Broken output:
{broken_text}
"""


def _validate_plan_structure(plan: Dict[str, Any], total_days: int) -> None:
    if not isinstance(plan, dict):
        raise ValueError("Plan must be a JSON object")

    if "phases" not in plan or "daily_plan" not in plan:
        raise ValueError("Missing required keys: phases, daily_plan")

    phases = plan["phases"]
    daily = plan["daily_plan"]

    if not isinstance(phases, list):
        raise ValueError("phases must be a list")
    if not isinstance(daily, list):
        raise ValueError("daily_plan must be a list")
    if len(daily) != total_days:
        raise ValueError(f"daily_plan length must equal total_days ({total_days})")

    for i, day in enumerate(daily, start=1):
        if not isinstance(day, dict):
            raise ValueError(f"daily_plan[{i}] must be an object")

        for key in ("day_index", "phase", "main_topic", "tasks"):
            if key not in day:
                raise ValueError(f"daily_plan[{i}] missing field: {key}")

        if not isinstance(day["day_index"], int):
            raise ValueError(f"daily_plan[{i}].day_index must be int")
        if day["day_index"] != i:
            raise ValueError(f"daily_plan[{i}].day_index must be {i}")

        if not isinstance(day["phase"], str) or not day["phase"].strip():
            raise ValueError(f"daily_plan[{i}].phase must be non-empty string")
        if not isinstance(day["main_topic"], str) or not day["main_topic"].strip():
            raise ValueError(f"daily_plan[{i}].main_topic must be non-empty string")

        tasks = day["tasks"]
        if not isinstance(tasks, list) or not tasks:
            raise ValueError(f"daily_plan[{i}].tasks must be a non-empty list")
        if not all(isinstance(t, str) and t.strip() for t in tasks):
            raise ValueError(f"daily_plan[{i}].tasks must contain non-empty strings")


def _enrich_daily_plan(
    plan: Dict[str, Any],
    all_days: List[date],
    hours_per_day: float,
    focus: str,
) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for idx, d in enumerate(all_days, start=1):
        item = plan["daily_plan"][idx - 1]
        enriched.append(
            {
                "day_index": idx,
                "date": d.isoformat(),
                "phase": item["phase"],
                "hours": hours_per_day,
                "focus": focus,
                "main_topic": item["main_topic"],
                "tasks": item["tasks"],
            }
        )
    return enriched


def task_planner(
    exam_date: str,
    hours_per_day: float = 2.0,
    focus: str = "practice_coding",
    start_date: str | None = None,
    final_practice_days: int = 10,
    model_name: str | None = None,
    api_key: str | None = None,
    use_llm: bool = True,
) -> Dict[str, Any]:
    today = date.today()
    start = _parse_date(start_date) if start_date else today
    exam = _parse_date(exam_date)

    if exam < start:
        raise ValueError("exam_date must be >= start_date")
    if hours_per_day <= 0:
        raise ValueError("hours_per_day must be > 0")
    if final_practice_days < 0:
        raise ValueError("final_practice_days must be >= 0")
    if not use_llm:
        raise ValueError("use_llm=False is not supported in no-hardcode mode")

    all_days = _date_range(start, exam)
    total_days = len(all_days)
    total_hours = round(total_days * hours_per_day, 2)

    resolved_model_name = (
        model_name
        or os.getenv("GEMINI_MODEL")
        or "gemini-2.5-flash"
    )
    resolved_api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not resolved_api_key:
        raise ValueError("Missing GEMINI_API_KEY")

    llm = GeminiProvider(model_name=resolved_model_name, api_key=resolved_api_key)

    prompt = _build_planner_prompt(
        start_iso=start.isoformat(),
        exam_iso=exam.isoformat(),
        total_days=total_days,
        hours_per_day=hours_per_day,
        final_practice_days=final_practice_days,
        focus=focus,
    )

    max_attempts = 3
    raw_text = ""
    last_error: Exception | None = None
    parsed: Dict[str, Any] | None = None

    for attempt in range(max_attempts):
        try:
            if attempt == 0:
                resp = llm.generate(prompt)
            else:
                repair_prompt = _build_repair_prompt(
                    broken_text=raw_text,
                    error_msg=str(last_error),
                    total_days=total_days,
                    hours_per_day=hours_per_day,
                )
                resp = llm.generate(repair_prompt)

            raw_text = resp["content"]
            candidate = _extract_first_json_object(raw_text)
            _validate_plan_structure(candidate, total_days)
            parsed = candidate
            break
        except Exception as e:
            last_error = e

    if parsed is None:
        raise ValueError(f"Task_Planner failed after {max_attempts} attempts: {last_error}")

    phases = parsed["phases"]
    daily_plan = _enrich_daily_plan(parsed, all_days, hours_per_day, focus)

    return {
        "input": {
            "start_date": start.isoformat(),
            "exam_date": exam.isoformat(),
            "hours_per_day": hours_per_day,
            "focus": focus,
            "final_practice_days": final_practice_days,
            "use_llm": use_llm,
            "provider": "google",
            "model_name": resolved_model_name,
        },
        "summary": {
            "total_days": total_days,
            "total_hours": total_hours,
            "message": f"Plan generated for {total_days} days, {hours_per_day} hours/day.",
        },
        "phases": phases,
        "daily_plan": daily_plan,
    }


def get_task_planner_tool() -> Dict[str, Any]:
    return {
        "name": "Task_Planner",
        "description": (
            "Create a day-by-day ML study plan with Gemini API. "
            "Args: exam_date, hours_per_day, focus, start_date, final_practice_days, model_name. "
            "Returns JSON with phases and daily_plan."
        ),
        "func": task_planner,
    }