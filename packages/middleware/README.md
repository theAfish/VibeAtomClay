# AtomClay Backend

This is the middle-layer API that connects the AtomClay frontend to the Agentom server.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the server:
   ```bash
   python main.py
   ```

The server will run on `http://localhost:3000`.

## Endpoints

- `POST /create_session`: Creates a new session with unique user_id and session_id by calling the Agentom server.
  - Response: `{"user_id": "u_xxx", "session_id": "s_xxx"}`

- `POST /run`: Forwards the request to the Agentom server's `/run` endpoint. The frontend should use the user_id and session_id obtained from `/create_session`.

- `POST /send_message`: Sends a message to a specific session.
  - Request: `{"user_id": "u_xxx", "session_id": "s_xxx", "message": "user input"}`
  - Response: The agent's response.

## Environment Variables

- `AGENTOM_BASE_URL`: The base URL of the Agentom server (default: `http://localhost:8000`)