from __future__ import annotations
import uvicorn
from linkground.config import API_HOST, API_PORT

def main() -> None:
    uvicorn.run('linkground.api.app:app', host=API_HOST, port=API_PORT, reload=False)
if __name__ == '__main__':
    main()
