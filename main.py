import requests
import yfinance as yf
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import io
import base64
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from jinja2 import Template
from langchain_openai import ChatOpenAI
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
    """ Получает цену акций. """
    ticker = COMPANY_TICKERS.get(company_name.lower())

    if not ticker:
        return None, f"Компания '{company_name}' не найдена в базе."

    stock = yf.Ticker(ticker)
    data = stock.history(period="7d")

    if data.empty:
        return None, f"Не удалось найти данные по акции {ticker}."

    # Возвращаем только цену акции
    return f"Текущая цена {company_name} ({ticker}): {data['Close'].iloc[-1]:.2f} USD", f"Цена акции: {data['Close'].iloc[-1]:.2f} USD"



def get_news_summary(query: str):
    """ Получает новости и делает выжимку через LLM. """
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    response = requests.get(rss_url)

    if response.status_code != 200:
        return "Ошибка при получении новостей.", "", ""  # Возвращаем пустые строки, если ошибка

    root = ET.fromstring(response.content)
    items = root.findall(".//item")

    if not items:
        return "Не найдено новостей по данной теме.", "", ""  # Возвращаем пустые строки, если новостей нет

    news_texts = []
    for item in items[:3]:
        title = item.find("title").text
        description = item.find("description")
        text = description.text if description is not None else title
        news_texts.append(f"{title}: {text}")
    
    summary_prompt = f"Создай краткую сводку по этим новостям: {' '.join(news_texts)}"
    summary = chat_with_llama(summary_prompt)

    return "Новости по теме:", news_texts, summary  # Возвращаем три значения

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
        <title>Чат с ИИ</title>
        <style>
            /* Стиль для блока чата */
            #chat {
                max-height: 400px;
                overflow-y: auto;
                margin-bottom: 10px;
                padding: 10px;
                border: 1px solid #ccc;
                background-color: #f9f9f9;
                border-radius: 5px;
            }
            .user-message {
                text-align: right;
                background-color: #d4edda;
                border-radius: 10px;
                padding: 5px;
                margin-bottom: 5px;
            }
            .ai-message {
                text-align: left;
                background-color: #f0f0f0;
                border-radius: 10px;
                padding: 5px;
                margin-bottom: 5px;
            }
        </style>
    </head>
    <body>
        <h2>Введите запрос:</h2>
        <input type="text" id="query" placeholder="Введите запрос" size="40">
        <button onclick="sendMessage()">Отправить</button>
        <div id="chat"></div>

        <script>
            let ws = new WebSocket("ws://" + location.host + "/ws");

            ws.onmessage = function(event) {
                let chat = document.getElementById("chat");
                chat.innerHTML += "<div class='ai-message'>" + event.data + "</div>";
                chat.scrollTop = chat.scrollHeight;  // Прокрутка вниз
            };

            // Функция отправки сообщения
            function sendMessage() {
                let input = document.getElementById("query");
                if (input.value.trim()) {
                    let chat = document.getElementById("chat");
                    chat.innerHTML += "<div class='user-message'>" + input.value + "</div>";
                    ws.send(input.value);
                    input.value = "";  // Очищаем поле ввода
                    chat.scrollTop = chat.scrollHeight;  // Прокручиваем чат вниз
                }
            }

            // Обработчик клавиши Enter
            document.getElementById("query").addEventListener("keypress", function(event) {
                if (event.key === "Enter") {
                    sendMessage();  // Отправка сообщения при нажатии Enter
                }
            });
        </script>
    </body>
</html>

    """)
    return template.render()



@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        query = await websocket.receive_text()
        if re.search(r"как обстоят дела с\s+(.+)", query, re.IGNORECASE):
            company_name = re.search(r"как обстоят дела с\s+(.+)", query, re.IGNORECASE).group(1)
            _, price_message = get_stock_price(company_name)  # Получаем только сообщение с ценой
            _, _, summary = get_news_summary(company_name)  # Получаем только выжимку новостей

            # Формируем ответ с ценой и выжимкой новостей
            response_message = f"Цена акции: {price_message}<br>Выжимка: {summary}"
            await websocket.send_text(response_message)
        else:
            ai_response = chat_with_llama(query)  # Ответ ИИ на другие запросы
            await websocket.send_text(ai_response)





if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
