
WEEK 9  ·  MODULE 5  ·  MCP, MULTI-AGENT & A2A
MCP — the Standard Way Agents Reach Tools & Data
Build Week
Connect your agent to tools the standard way (MCP), and build one that others can plug into.
At a glance
Module	Week 9 · Module 5 — MCP, Multi-agent & A2A
Format	Build week — hands-on, one deliverable
Deliverable	An agent that discovers tools over MCP, plus your own MCP server another person's agent can call
Mentor review	Friday — informal, no marks
Evaluated	Week 10 · Monday

What this week is about
Right now every tool you give the agent is wired in by hand, and no other team can reuse it. MCP is an industry standard — a common “socket” — for connecting AIs to tools and data. This week you connect your agent to tools through MCP, and expose one of your own so others can use it.
Why it matters
What problem does MCP solve?
Today every tool is custom-built for one app. MCP is a shared standard, so a tool you build can be reused by any AI, and any tool can plug into your agent.	Does MCP make my AI smarter?
No — it’s plumbing. It wins on reuse and easy swapping, not on answer quality. That’s the honest framing to give a client.	Where does the AI actually run?
On your side (the “host”), never on the tool server. The server just offers tools; it has no idea which AI is calling.

What you’ll learn
•	What MCP is: a standard socket connecting AIs to tools and data
•	The three roles — host, client, server — and where the AI actually runs
•	Looking at the raw messages once, so MCP stops being a mystery
•	Connecting your agent so it discovers tools automatically instead of hard-coding them
•	Building your own small MCP server that exposes one real thing your app can do
•	Keeping it safe: access control, and checking a tool before you trust someone else’s
Topics covered
The exact concepts to study.
•  What MCP is	•  Host, client, server
•  Where the AI runs	•  Tools, resources, prompts
•  Transports (stdio, HTTP)	•  JSON-RPC handshake
•  Tool discovery	•  Building a server (fastmcp)
•  Recoverable errors	•  Remote MCP & auth

Your task this week
Evaluated: Week 10 · Monday
Connect your agent to a tool over MCP so it discovers the tool instead of you wiring it in. Then build a small MCP server that exposes one real capability of your app, and have someone else’s agent call it.
