import requests
import yfinance as yf
import xml.etree.ElementTree as ET
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from jinja2 import Template
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage

# API-ключ для Together AI
TOGETHER_API_KEY = "64c2965ad385c714dba03db71b6fd40aa2253c895bbb4f20ce8f50517637b188"

# Словарь с компаниями и их тикерами
COMPANY_TICKERS = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "meta": "META",
    "facebook": "META",
    "amazon": "AMZN",
    "tesla": "TSLA",
    "nvidia": "NVDA",
    "netflix": "NFLX",
    "intel": "INTC",
    "amd": "AMD",
    "ibm": "IBM",
    "twitter": "TWTR",
    "snapchat": "SNAP",
    "paypal": "PYPL",
    "starbucks": "SBUX",
    "coca-cola": "KO",
    "pepsi": "PEP",
    "boeing": "BA",
    "ford": "F",
    "general motors": "GM",
    "uber": "UBER",
    "lyft": "LYFT",
    "zoom": "ZM"
}

# FastAPI app
app = FastAPI()

# LLM модель
llm = ChatOpenAI(
    model_name="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
    openai_api_key=TOGETHER_API_KEY,
    openai_api_base="https://api.together.xyz/v1"
)

def get_stock_price(company_name: str):
    """ Получает цену акций. """
    ticker = COMPANY_TICKERS.get(company_name.lower())
    if not ticker:
        return f"Компания '{company_name}' не найдена в базе."
    stock = yf.Ticker(ticker)
    data = stock.history(period="1d")
    if data.empty:
        return f"Не удалось найти данные по акции {ticker}."
    return f"Текущая цена {company_name} ({ticker}): {data['Close'].iloc[-1]:.2f} USD"

def get_news_summary(query: str):
    """ Получает новости и делает выжимку через LLM. """
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    response = requests.get(rss_url)
    if response.status_code != 200:
        return "Ошибка при получении новостей."
    root = ET.fromstring(response.content)
    items = root.findall(".//item")
    if not items:
        return "Не найдено новостей по данной теме."
    news_texts = []
    for item in items[:3]:
        title = item.find("title").text
        news_texts.append(f"{title}")
    summary_prompt = f"Создай краткую сводку по этим новостям: {' '.join(news_texts)}"
    summary = chat_with_llama(summary_prompt)
    return f"Новости по теме {query}: {summary}"

def chat_with_llama(prompt: str):
    """ Общение с LLaMA 3 через LangChain. """
    try:
        response = llm([HumanMessage(content=prompt)])
        return response.content
    except Exception as e:
        return f"Ошибка общения с LLaMA: {str(e)}"

@app.get("/", response_class=HTMLResponse)
def home():
    template = Template("""
    <html>
        <head>
            <title>Чат-аналитик</title>
            <style>
                body { font-family: Arial, sans-serif; }
                #chat-box { width: 60%; height: 400px; overflow-y: auto; border: 1px solid #ccc; padding: 10px; margin-bottom: 10px; }
                .user { color: blue; }
                .bot { color: green; }
            </style>
        </head>
        <body>
            <h2>Финансовый чат-аналитик</h2>
            <div id="chat-box"></div>
            <input type="text" id="query" placeholder="Введите запрос..." size="40">
            <button onclick="sendQuery()">Отправить</button>

            <script>
                function sendQuery() {
                    let query = document.getElementById("query").value;
                    let chatBox = document.getElementById("chat-box");
                    chatBox.innerHTML += `<p class='user'><b>Вы:</b> ${query}</p>`;
                    fetch(`/ask?query=${query}`)
                        .then(response => response.text())
                        .then(data => {
                            chatBox.innerHTML += `<p class='bot'><b>Бот:</b> ${data}</p>`;
                            document.getElementById("query").value = "";
                        });
                }
            </script>
        </body>
    </html>
    """)
    return template.render()

@app.get("/ask", response_class=HTMLResponse)
def ask(query: str):
    if query.lower().startswith("как обстоят дела с"):
        company = query.lower().replace("как обстоят дела с", "").strip()
        price_info = get_stock_price(company)
        news_info = get_news_summary(company)
        return f"{price_info}<br><br>{news_info}"
    return chat_with_llama(query)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
