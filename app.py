import streamlit as st
from google import genai
from google.genai import types

MODEL = "gemini-3.8-flash"

SYSTEM_PROMPT = """
أنت مهندس إنشائي خبير ومساعد متخصص في الهندسة المدنية - قسم الإنشاءات فقط.

النطاق:
- التحليل الإنشائي: جسور، إطارات، جمالونات، بلاطات، جدران، أعمدة. حساب ردود
  الأفعال والقوى الداخلية (M, V, N) والهطول، بالطرق المناسبة (التوازن،
  slope-deflection، توزيع العزوم، مصفوفة الجساءة).
- التصميم: خرسانة مسلحة وفولاذ وأساسات، مع تحقق حدود المقاومة والخدمة.
- الأحمال وتراكيبها وفق EN 1990/1991 وASCE 7.
- قراءة المخططات والصور وملفات PDF.

الكودات: الكود الأوروبي (EN 1990-1998) والكود الأمريكي (ACI 318, ASCE 7, AISC 360).

قواعد صارمة:
1. أجب بالعربية، واكتب المصطلحات والرموز بالإنجليزية (As, fck, f'c, γc ...).
2. نظام الوحدات SI (kN, kN.m, MPa, mm) ما لم يطلب المستخدم غير ذلك.
3. في المسائل التصميمية، إذا لم يحدد المستخدم الكود فاسأله: EN أم ACI؟
   ولا تخلط معاملات الأمان أو الأحمال بين الكودين أبداً.
4. كل العمليات الحسابية الرقمية نفّذها باستخدام أداة تنفيذ الكود (Python)،
   وتحقق من الاتزان (ΣF=0, ΣM=0) في كل تحليل.
5. عند قراءة صورة أو PDF: اذكر أولاً ما قرأته (الأبعاد، الأحمال، المواد، الأسناد).
   إذا كان أي رقم غير واضح فاسأل المستخدم ولا تخمّن أبداً.
6. اعرض الحل خطوة بخطوة: المعطيات، الفرضيات، النموذج الإنشائي، التحليل، التصميم،
   التحقق، النتيجة.
7. اذكر رقم البند أو المعادلة من الكود. إذا لم تكن متأكداً فقل ذلك ولا تخترع أرقاماً.
8. إذا كان المنشأ معقداً (إطار فراغي كبير، تحليل ديناميكي أو زلزالي أو لاخطي)،
   وضّح أن الحل اليدوي تقريبي وأنه يلزم التحقق ببرنامج مثل ETABS أو SAP2000.
9. اختم كل إجابة تصميمية بتنبيه قصير: النتائج استرشادية وتحتاج مراجعة مهندس مرخّص.
10. إذا كان السؤال خارج مجال الإنشاءات، اعتذر بلطف وأخبر المستخدم أنك متخصص
    في الإنشاءات فقط.
"""

st.set_page_config(page_title="مساعد الإنشاءات", page_icon="🏗️")
st.markdown(
    "<style>.stChatMessage{direction:rtl;text-align:right;}</style>",
    unsafe_allow_html=True,
)
st.title("🏗️ مساعد الهندسة الإنشائية")
st.caption(
    "EN Eurocodes + ACI | يمكنك رفع صور وملفات PDF | "
    "النتائج استرشادية وتحتاج مراجعة مهندس مرخّص"
)

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        if m.get("files"):
            st.caption("📎 " + "، ".join(f["name"] for f in m["files"]))
        st.markdown(m["text"])
        if m.get("code"):
            with st.expander("عرض كود الحسابات (للمراجعة)"):
                st.code(m["code"], language="python")

prompt = st.chat_input(
    "اكتب سؤالك أو ارفع صورة/PDF...",
    accept_file="multiple",
    file_type=["png", "jpg", "jpeg", "webp", "pdf"],
)

if prompt:
    user_text = prompt.text or "حلل الملفات المرفقة."
    files = [
        {"name": f.name, "mime": f.type, "data": f.getvalue()}
        for f in (prompt.files or [])
    ]
    st.session_state.messages.append(
        {"role": "user", "text": user_text, "files": files}
    )
    with st.chat_message("user"):
        if files:
            st.caption("📎 " + "، ".join(f["name"] for f in files))
        st.markdown(user_text)

    contents = []
    for m in st.session_state.messages:
        parts = []
        for f in m.get("files", []):
            parts.append(types.Part.from_bytes(data=f["data"], mime_type=f["mime"]))
        parts.append(types.Part(text=m["text"]))
        contents.append(
            types.Content(
                role="user" if m["role"] == "user" else "model", parts=parts
            )
        )

    with st.chat_message("assistant"):
        with st.spinner("جاري التحليل..."):
            code_used = ""
            try:
                response = client.models.generate_content(
                    model=MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.2,
                        tools=[
                            types.Tool(code_execution=types.ToolCodeExecution())
                        ],
                    ),
                )
                answer = response.text or "لم أستطع توليد إجابة، أعد المحاولة."
                for part in response.candidates[0].content.parts:
                    if getattr(part, "executable_code", None):
                        code_used += part.executable_code.code + "\n\n"
            except Exception as e:
                answer = f"حدث خطأ: {e}"
        st.markdown(answer)
        if code_used:
            with st.expander("عرض كود الحسابات (للمراجعة)"):
                st.code(code_used, language="python")

    st.session_state.messages.append(
        {"role": "assistant", "text": answer, "files": [], "code": code_used}
      )
