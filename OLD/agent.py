from langchain_ollama import ChatOllama
from langchain.agents import initialize_agent, AgentType
from tools import list_files, read_file

# modelo local
llm = ChatOllama(
    model="qwen2.5:7b",
    temperature=0
)

tools = [list_files, read_file]

agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

while True:
    question = input("\nPregunta: ")

    if question == "exit":
        break

    response = agent.run(question)

    print("\nRespuesta:")
    print(response)