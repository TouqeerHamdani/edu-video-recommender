## 2024-05-24 - [Fix] Prevent Upstream Error Leakage in Auth Routes
**Vulnerability:** Supabase raw error details were leaked to the client during registration and login failures (`detail=f"Invalid credentials: {str(e)}"` and `detail=f"Upstream error: {err_str}"`).
**Learning:** Detailed upstream error messages (especially from external auth providers like Supabase) should never be exposed to clients as they can reveal internal application state, database details, or specific failure reasons that assist attackers in enumerating valid accounts or bypassing security controls.
**Prevention:** Catch upstream exceptions, log the full error stack internally via `logging.exception()`, and return generic, sanitised messages to the client (e.g., "Registration failed", "Invalid credentials").
