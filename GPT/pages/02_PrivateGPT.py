import streamlit as st
from langchain.chat_models import ChatOpenAI
from langchain.document_loaders import UnstructuredFileLoader
from langchain.callbacks import StreamingStdOutCallbackHandler
from langchain.callbacks.base import BaseCallbackHandler
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import Chroma, FAISS
from langchain.embeddings import OpenAIEmbeddings, CacheBackedEmbeddings
from langchain.storage import LocalFileStore
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema.runnable import RunnablePassthrough, RunnableLambda
from langchain.memory import ConversationSummaryBufferMemory


class ChatCallbackHandler(BaseCallbackHandler):
    message = ""

    def on_llm_start(self, *args, **kwargs):
        self.message_box = st.empty()

    def on_llm_end(self, *args, **kwargs):
        save_message(self.message, "ai")

    def on_llm_new_token(self, token, *args, **kwargs):
        self.message += token
        self.message_box.markdown(self.message)


chat = ChatOpenAI(
    #                 model="gpt-4.1-nano",
    temperature=0.1,
    tiktoken_model_name="gpt-3.5-turbo",
    streaming=True,
    callbacks=[
        ChatCallbackHandler()
    ]
)

if "memory" not in st.session_state:
    st.session_state["memory"] = ConversationSummaryBufferMemory(
        llm=chat,
        max_token_limit=120,
        return_messages=False
    )

memory = st.session_state["memory"]


@st.cache_data(show_spinner="Embedding file...")
def embed_file(file):
    file_content = file.read()
    file_path = f"./cache/private_files/{file.name}"
    with open(file_path, "wb") as f:
        f.write(file_content)
    cache_dir = LocalFileStore(f"./cache/private_embeddings/{file.name}")

    splitter = CharacterTextSplitter.from_tiktoken_encoder(
        separator="\n",
        chunk_size=600,
        chunk_overlap=100,
    )
    loader = UnstructuredFileLoader(file_path)
    docs = loader.load_and_split(text_splitter=splitter)
    embeddings = OpenAIEmbeddings()
    cached_embeddings = CacheBackedEmbeddings.from_bytes_store(
        embeddings, cache_dir
    )
    vectorstore = FAISS.from_documents(docs, cached_embeddings)
    retriever = vectorstore.as_retriever()
    return retriever


def save_message(message, role):
    st.session_state["messages"].append({"message": message, "role": role})


def send_message(message, role, save=True):
    with st.chat_message(role):
        st.markdown(message)
    if save:
        save_message(message, role)


def paint_history():
    for message in st.session_state["messages"]:
        send_message(message["message"], message["role"], save=False)


def format_docs(docs):
    return "\n\n".join(document.page_content for document in docs)


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
            Answer the question using ONLY the following context. If you don't know the answer just say you don't know. DON'T make anything up.

            Context: {context}
            """,
        ),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{question}"),
    ]
)

st.title("PrivateGPT")

st.markdown("""
Welcome!

Use this chatbot to ask question to an AI about your files!

Upload your file on the sidebar.
""")

with st.sidebar:
    file = st.file_uploader("Upload a .txt or .docx file", type=["txt", "docx"])

if file:
    retriever = embed_file(file)
    send_message("I'm ready! Ask away", "ai", save=False)
    paint_history()
    message = st.chat_input("Ask anything about your file...")

    if message:
        send_message(message, "human")
        # chain =  {
        #     "context": retriever | RunnableLambda(format_docs),
        #      "history": RunnableLambda(
        #          lambda _: memory.load_memory_variables({})["history"]
        #      ),
        #     "question" : RunnablePassthrough(),
        # } | prompt | chat

        chain = RunnablePassthrough.assign(
            history=lambda x: memory.load_memory_variables({})["history"]
        ) | {
                    "context": RunnableLambda(lambda x: x["question"]) | retriever | RunnableLambda(format_docs),
                    "question": RunnableLambda(lambda x: x["question"]),
                    "history": RunnableLambda(lambda x: x["history"]),
                } | prompt | chat

        # same as chain
        # docs = retriever.invoke(message)
        # # docs = "\n\n".join(document.page_content for document in docs)
        # prompt = prompt.format_messages(context=docs, question = message)
        # chat.predict_messages(prompt)

        with st.chat_message("ai"):
            result = chain.invoke({"question": message})
            memory.save_context({"input": message}, {"output": result.content})

            # result = chain.invoke(message)
            # memory.save_context({"input": message}, {"output": result.content})


else:
    st.session_state["messages"] = []

