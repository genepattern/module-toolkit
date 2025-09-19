from pydantic_ai import Agent, RunContext


system_prompt = """
You are a PhD-level bioinformatician, knowledgeable in genetics, genomics, computational biology, 
machine learning and data analysis. Your task is to research bioinformatic tools and methods, 
reporting on their capabilities, dependencies, applications and configurable parameters. You 
should be thorough, accurate and concise in your responses. Always cite your sources when providing 
information.
"""

researcher_agent = Agent('bedrock:us.anthropic.claude-sonnet-4-20250514-v1:0', system_prompt=system_prompt)


@researcher_agent.tool
def web_search(context: RunContext[str]) -> str:
    # TODO: Implement Brave AI search here
    return ''
