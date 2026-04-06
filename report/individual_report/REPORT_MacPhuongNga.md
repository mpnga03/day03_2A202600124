# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Mạc Phương Nga
- **Student ID**: 2A202600124
- **Date**: 06/04/2026

---

## I. Technical Contribution (15 Points)

*Describe your specific contribution to the codebase (e.g., implemented a specific tool, fixed the parser, etc.).*

- **Modules Implementated**:  `src/tools/calculator.py`
- **Code Highlights**: 
```python
from datetime import datetime
from src.core.llm_provider import LLMProvider

def calculate_date_with_llm(args_str: str, llm: LLMProvider) -> str:
    """
    Tool tính ngày tháng sử dụng LLMProvider để đọc hiểu ngôn ngữ tự nhiên.
    Luôn trả về chuỗi chứa một số nguyên. Trả về "-1" nếu lỗi.
    """
    args_str = args_str.strip("'\" ")
    if not args_str:
        return "-1"
        
    # 1. Lấy mốc thời gian thực tế của hệ thống
    now = datetime.now()
    today_str = now.strftime('%d/%m/%Y')
    
    # 2. Xây dựng System Prompt & User Prompt bằng tiếng Anh
    system_prompt = """
    You are a time analysis tool. 
    Your task is to read the request and determine how many days the user wants you to schedule for their study plan.
    Return the number of days as an integer.
    If the user's request is a general question without a specific timeframe, return a suggested reasonable number of days based on the context. 
    If the duration cannot be determined at all, return -1.
    ABSOLUTELY NO explanations, NO punctuation marks. If you cannot calculate it, return -1.
    """
    
    user_prompt = f"Today is {today_str}. User request: '{args_str}'"
    
    try:
        # 3. Gọi LLM thông qua provider được truyền vào
        result_dict = llm.generate(prompt=user_prompt, system_prompt=system_prompt)
        
        # 4. Trích xuất text từ dictionary trả về
        llm_response = result_dict["content"].strip()
        
        # 5. Parse kết quả
        so_ngay = int(llm_response)
            
        return str(so_ngay)
        
    except ValueError:
        return "-1"
    except Exception as e:
        return "-1"
```
- **Documentation**: 
Hàm `calculate_date_with_llm` được thiết kế như một tool trong hệ thống ReAct Agent. Hàm được sử dụng để tính toán số ngày còn lại/cần thiết cho một kế hoạch học tập dựa trên yêu cầu của người dùng. Điểm đặc biệt của tool này là nó sử dụng một LLM (Language Model) để hiểu và phân tích ngôn ngữ tự nhiên trong yêu cầu, từ đó đưa ra con số ngày phù hợp. Hàm trả về một chuỗi chứa số nguyên đại diện cho số ngày, hoặc "-1" nếu có lỗi xảy ra hoặc nếu không thể xác định được số ngày từ yêu cầu. Tool này giúp Agent có khả năng xử lý các yêu cầu liên quan đến thời gian một cách linh hoạt và chính xác hơn.
---

## II. Debugging Case Study (10 Points)

*Analyze a specific failure event you encountered during the lab using the logging system.*

- **Problem Description**:
Trong quá trình test, gặp một lỗi khi Agent chỉ gọi `search` và `calculator` mà không gọi `taskplanner` để phân bổ nội dung học tập vào lịch trình, dẫn đến việc chỉ có các nội dung cần học.
- **Log Source**:
```
{"timestamp": "2026-04-06T10:23:55.378735", "event": "AGENT_START", "data": {"input": "I want to apply to the university's Artificial Intelligence Lab (AI Lab) at the end of this month. Could you help me find some basic Machine Learning study materials and schedule a 2-hour daily practical study session from now until the exam?", "model": "gemini-2.5-flash"}}
{"timestamp": "2026-04-06T10:24:00.836122", "event": "TOOL_CALL", "data": {"tool": "search", "args": "\"basic machine learning study materials for AI lab admission\"", "result": "1.  Introduction to Machine Learning: Definition, types (supervised, unsupervised, reinforcement), common applications.\n2.  Fundamental Concepts: Data types, features, labels, training vs. testing data, basic statistics for ML.\n3.  Supervised Learning Basics: Linear Regression (concept, cost function), Logistic Regression (binary classification), introduction to Decision Trees.\n4.  Unsupervised Learning Basics: K-Means Clustering (concept, use cases).\n5.  Model Evaluation & Improvement: Overfitting/underfitting, cross-validation, basic performance metrics (accuracy, precision, recall)."}}
{"timestamp": "2026-04-06T10:24:04.206446", "event": "TOOL_CALL", "data": {"tool": "calculate_date", "args": "\"end of this month\"", "result": "26"}}
{"timestamp": "2026-04-06T10:24:10.137692", "event": "AGENT_END", "data": {"steps": 3, "status": "success"}}
```
- **Diagnosis**:
Dựa trên log, Agent đã gọi `search` để tìm tài liệu học tập và `calculate_date` để tính số ngày còn lại, nhưng không gọi `taskplanner` để phân bổ nội dung vào lịch trình. Nguyên nhân có thể là do logic trong phần `Thought` của Agent chưa đủ mạnh để nhận ra rằng sau khi có số ngày và nội dung học, bước tiếp theo cần phải là phân bổ lịch học cụ thể.
- **Solution**:
Để khắc phục, tôi đã điều chỉnh logic trong phần `Thought` của Agent để đảm bảo rằng sau khi có được số ngày từ `calculator` và nội dung học từ `search`, Agent sẽ tự động nhận ra rằng cần phải gọi `taskplanner` để phân bổ nội dung vào lịch trình học tập. Cụ thể, tôi đã thêm một bước kiểm tra trong `Thought` để xác định xem nếu đã có đủ thông tin về số ngày và nội dung học, thì bước tiếp theo phải là gọi `taskplanner` với các tham số phù hợp.
---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

*Reflect on the reasoning capability difference.*

1.  **Reasoning**: How did the `Thought` block help the agent compared to a direct Chatbot answer?
* Task Breakdown: Với LLM Chatbot thông thường, khi được yêu cầu "lập lịch từ nay đến cuối tháng", nó sẽ sinh ra một lịch trình "ảo" dựa trên trí nhớ nội tại, thường sai lệch về số ngày thực tế. Khối Thought giúp Agent nhận ra nó thiếu thông tin và tự đặt câu hỏi: "Trước tiên mình cần tính xem từ hôm nay đến cuối tháng là bao nhiêu ngày".
* Lập kế hoạch tuần tự: `Thought` ép Agent tư duy theo chuỗi logic thay vì đoán mò: Tính số ngày (Calculator) --> Tìm nội dung ôn tập ML (Search) --> Phân bổ nội dung vào số ngày hiện có (Planner). Điều này giúp lịch học sinh ra bám sát thực tế toán học và khối lượng kiến thức.
2.  **Reliability**: In which cases did the Agent actually perform *worse* than the Chatbot?
* Độ trễ: Agent sử dụng nhiều tools hơn nên có thể chậm hơn Chatbot trong những câu hỏi đơn giản không cần suy luận sâu, ví dụ "Hôm nay là ngày mấy?" Chatbot có thể trả lời ngay, trong khi Agent phải qua Thought -> Action -> Observation mới có câu trả lời.
* Tool Failure: Nếu một tool như Calculator hoặc Search gặp lỗi (ví dụ API downtime), Agent có thể bị "đơ" hoặc trả về kết quả sai, trong khi Chatbot vẫn có thể đưa ra câu trả lời dựa trên kiến thức đã học.
3.  **Observation**: How did the environment feedback (observations) influence the next steps?
* Observations cung cấp ngữ cảnh động để định hướng hành động tiếp theo của Agent.
* Ví dụ: Khi Action 1 gọi Calculator và trả về Observation 1: Còn 25 ngày. Con số "25" này ngay lập tức được Agent đưa vào Thought 2 để làm tham số cho việc chia lịch. Nếu Observation trả về "Chỉ còn 3 ngày", Agent sẽ lập tức thay đổi chiến lược trong Thought tiếp theo thành: "Thời gian quá gấp, bỏ qua học lý thuyết, chuyển sang tìm bộ đề thực hành giải ngay lập tức".

---

## IV. Future Improvements (5 Points)

*How would you scale this for a production-level AI agent system?*

- **Scalability**:
    + Lưu trữ ngữ cảnh qua Vector Database: Thay vì chỉ nhớ các tin nhắn gần nhất, Agent sẽ sử dụng cơ sở dữ liệu vector (như Pinecone hoặc Milvus) để lưu trữ lịch sử học tập và sở thích của người dùng từ các phiên làm việc trước.
    + Cá nhân hóa lộ trình: Agent có thể nhận diện phong cách học tập (VD: người dùng thích thực hành hơn lý thuyết) để tự động điều chỉnh nội dung tìm kiếm từ `search` sao cho phù hợp nhất với từng cá nhân.
- **Safety**:
    + Con người kiểm soát (Human-in-the-Loop - HITL): Triển khai cơ chế bắt buộc phê duyệt đối với các Tool có khả năng thay đổi trạng thái hoặc tác vụ nhạy cảm (VD: hỏi rõ người dùng "Bạn có muốn tôi lưu lịch này vào Google Calendar không?" trước khi thực sự gọi API).
    + Rào chắn bảo vệ & Agent giám sát (Guardrails & Supervisor Agents): Triển khai một LLM nhẹ, tốc độ cao (hoặc bộ kiểm duyệt dựa trên luật) đóng vai trò 'Người giám sát' (Supervisor) để chặn và làm sạch đầu vào của người dùng khỏi các cuộc tấn công Prompt Injection, đồng thời kiểm duyệt các Action do ReAct Agent đề xuất trước khi chúng được thực thi.
- **Performance**:
    + Bộ nhớ đệm ngữ nghĩa (Semantic Caching): Tích hợp lớp cache (VD: Redis kết hợp vector search) để trả lời ngay lập tức các câu hỏi trùng lặp hoặc có ý nghĩa tương đương từ người dùng, giúp giảm thiểu độ trễ API và tiết kiệm tối đa chi phí token.
    + Truy xuất Tool động (Tool RAG): Khi số lượng Tool tăng lên, việc nhồi nhét toàn bộ mô tả Tool vào System Prompt sẽ làm cạn kiệt bộ nhớ ngữ cảnh (context window) và gây ra ảo giác (hallucination). Giải pháp là sử dụng Vector Database (như ChromaDB hoặc Pinecone) để truy xuất động và chỉ nạp vào top-K các Tool liên quan nhất với câu hỏi hiện tại của người dùng.

---
