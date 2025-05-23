from langchain.document_loaders import SitemapLoader, text
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.chat_models import ChatOpenAI
from langchain.schema.runnable import RunnablePassthrough, RunnableLambda
from langchain.prompts import ChatPromptTemplate
import streamlit as st
from bs4 import BeautifulSoup

llm = ChatOpenAI(
    model="gpt-4.1-nano",
    temperature=0.1,
    tiktoken_model_name="gpt-3.5-turbo",
)

answers_prompt = ChatPromptTemplate.from_template(
    """
    Using ONLY the following context answer the user's question. If you can't just say you don't know, don't make anything up.

    Then, give a score to the answer between 0 and 5.

    If the answer answers the user question the score should be high, else it should be low.

    Make sure to always include the answer's score even if it's 0.

    Context: {context}

    Examples:

    Question: How far away is the moon?
    Answer: The moon is 384,400 km away.
    Score: 5

    Question: How far away is the sun?
    Answer: I don't know
    Score: 0

    Your turn!

    Question: {question}
"""
)
def get_answer(inputs):
    docs = inputs['docs']
    question = inputs["question"]
    answers_chain = answers_prompt | llm
    answers = []
    for doc in docs:
        result = answers_chain.invoke({
            "question": question,
            "context" : doc.page_content
        })
        answers.append(result.content)
    st.write(answers)
def parse_page(soup:BeautifulSoup):
    header = soup.find("header")
    footer = soup.find("footer")
    if header:
        header.decompose()
    if footer:
        footer.decompose()
    return str(soup.get_text()).replace("\n"," ").replace("\na0"," ").replace("CloseSearch Submit Blog", "")

@st.cache_data(show_spinner="Loading website...")
def load_website(url):
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=1000,
        chunk_overlap=200,
    )
    loader = SitemapLoader(url,
    # filter_urls=[
    #    r"^(.*\/news\/).*",
    # ],
    parsing_function=parse_page,
    )
    loader.requests_per_second = 1
    docs = loader.load_and_split(text_splitter=splitter)
    vector_store = FAISS.from_documents(docs, OpenAIEmbeddings())
    return vector_store.as_retriever()

st.set_page_config(
    page_title="SiteGPT",
    page_icon="🖥️",
)

st.markdown(
    """
    # SiteGPT

    Ask questions about the content of a website.

    Start by writing the URL of the website on the sidebar.
"""
)

with st.sidebar:
    url = st.text_input(
        "Write down a URL",
        placeholder="https://example.com",
    )

if url:
    if ".xml" not in url:
        with st.sidebar:
            st.error("Please wirte down a Sitemap URL")
    else:
        retriver = load_website(url)

        chain = {"docs":retriver,
                 "question":RunnablePassthrough(),
                 } | RunnableLambda(get_answer)

        chain.invoke("What is the price of GPT-4 Turbo")