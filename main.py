import requests
import yfinance as yf
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import io
import base64
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from jinja2 import Template
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage
import re

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
    """ Получает цену акций и строит график. """
    ticker = COMPANY_TICKERS.get(company_name.lower())

    if not ticker:
        return None, f"Компания '{company_name}' не найдена в базе."

    stock = yf.Ticker(ticker)
    data = stock.history(period="7d")

    if data.empty:
        return None, f"Не удалось найти данные по акции {ticker}."

    # Построение графика
    plt.figure(figsize=(10, 5))
    plt.plot(data.index, data['Close'], marker='o', linestyle='-')
    plt.xlabel("Дата", fontsize=12)
    plt.ylabel("Цена (USD)", fontsize=12)
    plt.title(f"График цены {company_name} ({ticker})")
    plt.grid()

    # Сохранение графика в base64
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()

    return img_base64, f"Текущая цена {company_name} ({ticker}): {data['Close'].iloc[-1]:.2f} USD"

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

    articles = [item.find("title").text for item in items[:3]]

    # Создание выжимки через LLaMA
    summary_prompt = f"Создай краткую сводку по этим заголовкам: {articles}"
    summary = chat_with_llama(summary_prompt)

    return f"Новости по теме {query}:", articles, summary

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
            <title>Поиск</title>
        </head>
        <body>
            <h2>Введите запрос:</h2>
            <form action="/ask">
                <input type="text" name="query" placeholder="например, 'Apple' или 'новости Tesla'" size="40">
                <input type="submit" value="Искать">
            </form>
        </body>
    </html>
    """)
    return template.render()

@app.get("/ask", response_class=HTMLResponse)
def ask(query: str):
    # Проверка на запрос цены акций
    match = re.search(r"акции\s+(.+)|как обстоят дела с акциями\s+(.+)", query, re.IGNORECASE)
    if match:
        company_name = match.group(1) or match.group(2)
        img_base64, message = get_stock_price(company_name)

        if img_base64:
            template = Template("""
                <h2>{{ message }}</h2>
                <img src='data:image/png;base64,{{ img_base64 }}' width='600'>
            """)
            return template.render(message=message, img_base64=img_base64)
        return f"<h2>{message}</h2>"

    # Проверка на запрос новостей
    match = re.search(r"новости\s+(.+)|что нового в\s+(.+)", query, re.IGNORECASE)
    if match:
        topic = match.group(1) or match.group(2)
        title, articles, summary = get_news_summary(topic)
        template = Template("""
            <h2>{{ title }}</h2>
            <ul>
                {% for article in articles %}
                    <li>{{ article }}</li>
                {% endfor %}
            </ul>
            <h3>Выжимка:</h3>
            <p>{{ summary }}</p>
        """)
        return template.render(title=title, articles=articles, summary=summary)

    # Обработка общих вопросов
    ai_response = chat_with_llama(query)
    template = Template("""
        <h2>Ответ от AI:</h2>
        <p>{{ ai_response }}</p>
    """)
    return template.render(ai_response=ai_response)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
