# ADDA AI — short pitch

People move between code assistants, document readers and search tools, often losing track of where an answer came from. ADDA AI brings these tasks into one workspace and makes the selected capability, work performed and supporting evidence visible.

Our local MVP uses Next.js, FastAPI and LangGraph. A deterministic router selects Coding, Document, Search or Research. The strongest verified flow is document work: upload a PDF, retrieve a budget with a page citation, and run a Research workflow that plans two evidence checks and assembles a cited brief. It works without provider keys because it uses bounded keyword retrieval and real source excerpts.

LangGraph makes the workflow explicit: routing, planning, collection and reporting are separate executable steps. The UI displays the completed steps and actual response provider. This supports a clear distinction between retrieved evidence, a fixed Coding fixture and a future verified model response.

Coding has a Bedrock Converse integration, with live inference still pending. Search has a Tavily adapter; a prior local live request returned provider results when a key was configured. Our Research brief is extractive, not model-generated analysis or independent fact-checking. We do not claim embeddings or a vector database in this version.

AWS deployment is live in `ap-south-1`: Amplify frontend `https://main.dvhyzvzxczywv.amplifyapp.com/` and API Gateway/Lambda `https://pqrxb30pg5.execute-api.ap-south-1.amazonaws.com` (stack `adda-ai-demo`). Coding remains the labelled demo fixture until Bedrock inference is verified. Documents use private short-lived S3 evidence storage in the Lambda deployment. Semantic retrieval is still future work.

The demonstration shows a working, inspectable document workflow and an extensible graph architecture, with clear boundaries around what has actually been verified.
