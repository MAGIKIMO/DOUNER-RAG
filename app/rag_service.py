import os
import chromadb
from groq import Groq
from langchain_huggingface import HuggingFaceEmbeddings


class RAGService:
    def __init__(self):
        # 임베딩 모델
        self.embedding = HuggingFaceEmbeddings(
            model_name="jhgan/ko-sroberta-multitask",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )

        # ChromaDB 연결
        self.chroma_client = chromadb.HttpClient(
            host=os.getenv("CHROMA_HOST", "vector-db"),
            port=int(os.getenv("CHROMA_PORT", 8000)),
            tenant="default_tenant",
            database="default_database"
        )

        self.collection = self.chroma_client.get_or_create_collection(
            name="douner_collection"
        )

        # Groq 클라이언트
        self.groq_client = Groq(
            api_key=os.getenv("GROQ_API_KEY")
        )

    def get_answer(self, question: str, language: str = "ko"):
        try:
            # 1. 질문 임베딩
            query_embedding = self.embedding.embed_query(question)

            # 2. ChromaDB 검색
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=8
            )

            if not results or not results.get("documents"):
                return "관련 정보를 찾지 못했습니다.", "", []

            docs = results["documents"][0]
            metadatas = results.get("metadatas", [[]])[0]

            if not docs:
                return "관련 정보가 부족합니다.", "", []

            # 3. Context + Sources 구성
            context_parts = []
            sources = []
            seen_sources = set()

            for i, doc in enumerate(docs):
                meta = metadatas[i] if i < len(metadatas) else {}

                title = meta.get("title", "제목 없음")
                url = meta.get("url", "")
                category = meta.get("category", "")
                source_type = meta.get("source_type", "")

                context_parts.append(
                    f"[문서 {i + 1}]\n"
                    f"제목: {title}\n"
                    f"카테고리: {category}\n"
                    f"URL: {url}\n"
                    f"내용:\n{doc}"
                )

                # URL 기준 중복 제거, URL이 없으면 title 기준
                source_key = url if url else title

                if source_key not in seen_sources:
                    seen_sources.add(source_key)
                    sources.append({
                        "title": title,
                        "url": url,
                        "category": category,
                        "source_type": source_type
                    })

            # 참고 자료는 최대 3개까지만 표시
            sources = sources[:3]

            context = "\n\n".join(context_parts)
            context = context[:5000]

            if not context.strip():
                return "관련 정보가 부족합니다.", "", []

            # 4. 다국어 시스템 프롬프트
            system_prompts = {
                "ko": """
당신은 동아대학교 유학생과 재학생을 돕는 AI 안내 도우미입니다.

반드시 제공된 문서 내용만 기반으로 답변하세요.
문서에 없는 내용은 추측하지 마세요.

답변은 자연스럽고 간결하게 작성하세요.
URL은 답변 본문에 직접 쓰지 마세요.
참고 자료 제목과 URL은 시스템이 별도로 표시합니다.

졸업 가능 여부, 졸업학점, 평균평점, 졸업논문, 학사학위취득 유예, 조기졸업 질문에서는 다음을 지키세요.
- 사용자가 제시한 이수학점/평점/학과/입학년도/논문 조건을 문서의 기준과 비교하세요.
- 문서에 전공별 세부 기준이나 입학년도별 기준이 없으면 확정 판단하지 말고 추가 확인이 필요한 항목을 말하세요.
- 충족한 조건과 부족하거나 확인이 필요한 조건을 분리해서 답하세요.

답변 형식:
1. 핵심 답변
2. 근거가 된 학사안내/공지 제목
3. 필요한 경우 충족 조건, 부족 조건, 추가 확인 필요 항목 요약
""",
                "ja": """
あなたは東亜大学の留学生と在学生をサポートするAIアシスタントです。

必ず提供された文書内容のみに基づいて回答してください。
文書にない内容は推測しないでください。

回答は自然で簡潔に作成してください。
URLは回答本文に直接書かないでください。
参考資料のタイトルとURLはシステムが別途表示します。

回答形式:
1. 重要な回答
2. 関連するお知らせのタイトル
3. 必要に応じて日程、対象者、申請方法の要約
""",
                "en": """
You are an AI assistant supporting international students and students at Dong-A University.

Answer only based on the provided documents.
Do not guess information that is not included in the documents.

Write the answer clearly and concisely.
Do not include URLs directly in the answer body.
The system will display source titles and URLs separately.

For graduation eligibility, credits, GPA, thesis, degree completion deferment, or early graduation questions:
- Compare the user's credits/GPA/department/admission year/thesis status against the documented criteria.
- If department-specific or admission-year-specific criteria are missing from the documents, do not make a final determination.
- Separate satisfied conditions from missing or needs-confirmation items.

Answer format:
1. Key answer
2. Related academic guide or notice title
3. If needed, summarize satisfied conditions, missing conditions, and items requiring confirmation
""",
                "zh": """
你是帮助东亚大学留学生和在校生的AI助手。

请只根据提供的文档内容回答。
不要推测文档中没有的信息。

请简洁、自然地回答。
不要在正文中直接写URL。
系统会另外显示参考资料标题和URL。

回答格式:
1. 核心回答
2. 相关公告标题
3. 如有需要，概括日程、对象和申请方法
"""
            }

            system_prompt = system_prompts.get(language, system_prompts["ko"])

            # 5. Groq LLM 호출
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"[문서]\n{context}\n\n[질문]\n{question}"
                    }
                ],
                temperature=0.2,
                max_tokens=512
            )

            answer = response.choices[0].message.content

            return answer, context, sources

        except Exception as e:
            return f"에러 발생: {str(e)}", "", []