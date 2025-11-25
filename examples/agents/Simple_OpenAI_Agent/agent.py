from agents import function_tool, WebSearchTool, Agent, ModelSettings, TResponseInputItem, Runner, RunConfig, trace
from openai import AsyncOpenAI
from types import SimpleNamespace
from pydantic import BaseModel

# Tool definitions
@function_tool
def get_weather(location: str, unit: str):
  pass

web_search_preview = WebSearchTool(
  user_location={
    "type": "approximate",
    "country": None,
    "region": None,
    "city": None,
    "timezone": None
  },
  search_context_size="medium"
)
# Shared client for guardrails and file search
client = AsyncOpenAI()
ctx = SimpleNamespace(guardrail_llm=client)
my_agent = Agent(
  name="My agent",
  instructions="You are the planner agent. Produce an organised, ordered, executable list of sub tasks that achieves the parent goal. Keep each subtask concise but well defined. Note explicit deliverables and dependencies. ",
  model="gpt-4.1",
  tools=[
    get_weather,
    web_search_preview
  ],
  model_settings=ModelSettings(
    temperature=1,
    top_p=1,
    parallel_tool_calls=True,
    max_tokens=2048,
    store=True
  )
)


class WorkflowInput(BaseModel):
  input_as_text: str


# Main code entrypoint
async def run_workflow(workflow_input: WorkflowInput):
  with trace("New workflow"):
    state = {

    }
    workflow = workflow_input.model_dump()
    conversation_history: list[TResponseInputItem] = [
      {
        "role": "user",
        "content": [
          {
            "type": "input_text",
            "text": workflow["input_as_text"]
          }
        ]
      }
    ]
    my_agent_result_temp = await Runner.run(
      my_agent,
      input=[
        *conversation_history
      ],
      run_config=RunConfig(trace_metadata={
        "__trace_source__": "agent-builder",
        "workflow_id": "wf_69142c49783c8190be03974a9d41e72d092250b124c7dde3"
      })
    )

    conversation_history.extend([item.to_input_item() for item in my_agent_result_temp.new_items])

    my_agent_result = {
      "output_text": my_agent_result_temp.final_output_as(str)
    }
    filesearch_result = { "results": [
      {
        "id": result.file_id,
        "filename": result.filename,
        "score": result.score,
      } for result in client.vector_stores.search(vector_store_id="", query="", max_num_results=10)
    ]}
