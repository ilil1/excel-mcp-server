import logging
import os

import httpx
from mcp.server.fastmcp import FastMCP

# Get project root directory path for log file path.
# When using the stdio transmission method,
# relative paths may cause log files to fail to create
# due to the client's running location and permission issues,
# resulting in the program not being able to run.
# Thus using os.path.join(ROOT_DIR, "excel-mcp.log") instead.

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_FILE = os.path.join(ROOT_DIR, "excel-mcp.log")

# Initialize EXCEL_FILES_PATH variable without assigning a value
EXCEL_FILES_PATH = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        # Referring to https://github.com/modelcontextprotocol/python-sdk/issues/409#issuecomment-2816831318
        # The stdio mode server MUST NOT write anything to its stdout that is not a valid MCP message.
        logging.FileHandler(LOG_FILE)
    ],
)
logger = logging.getLogger("excel-mcp")
# Initialize FastMCP server
mcp = FastMCP(
    "excel-mcp",
    version="0.1.4",
    description="Excel MCP Server for manipulating Excel files",
    dependencies=["openpyxl>=3.1.2"],
    env_vars={
        "EXCEL_FILES_PATH": {
            "description": "Path to Excel files directory",
            "required": False,
            "default": EXCEL_FILES_PATH
        }
    }
)

LARAVEL_API_BASE = "https://api.test-spot.com/api/v1"

def get_api_map():
    return {
        "token_authentication": f"{LARAVEL_API_BASE}/authentication/token",
        "get_order_list": f"{LARAVEL_API_BASE}/orders/get"
    }

async def call_laravel(func_name: str, payload: dict, use_auth: bool = False):
    url = get_api_map().get(func_name)
    if not url:
        return {"error": "API 경로를 찾을 수 없습니다."}

    headers = {}
    if use_auth and auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.post(url, json=payload, headers=headers)
            res.raise_for_status()
            return res.json()
        except httpx.HTTPStatusError as e:
            # 개발 로그용
            print(f"[Laravel 오류] status={e.response.status_code}, body={e.response.text}")
            return {"error": "스케줄 조회 중 문제가 발생했습니다. 관리자에게 문의해주세요."}
        except Exception as e:
            print(f"[네트워크 오류] {str(e)}")
            return {"error": "서버와의 연결에 실패했습니다."}

@mcp.tool()
def validate_test_sc() -> str:
    return "성공"

@mcp.tool()
async def token_authentication(id: str, password: str, user_type: int):
    """
    사용자 로그인 후 토큰은 내부에 저장되며, 외부로는 노출되지 않습니다.
    """
    global auth_token
    response = await call_laravel("token_authentication", {
        "id": id,
        "password": password,
        "user_type": user_type
    })

    token = None
    try:
        token = response.get("token")
    except Exception:
        pass

    if token:
        auth_token = token
        print("✅ 로그인 성공. 토큰 저장됨.")
        return {"message": "로그인 성공"}
    else:
        print("❌ 로그인 실패:", response)
        return {"error": "로그인 실패"}


async def run_sse():
    """Run Excel MCP server in SSE mode."""
    # Assign value to EXCEL_FILES_PATH in SSE mode
    global EXCEL_FILES_PATH
    EXCEL_FILES_PATH = os.environ.get("EXCEL_FILES_PATH", "./excel_files")
    # Create directory if it doesn't exist
    os.makedirs(EXCEL_FILES_PATH, exist_ok=True)

    try:
        logger.info(f"Starting Excel MCP server with SSE transport (files directory: {EXCEL_FILES_PATH})")
        await mcp.run_sse_async()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        await mcp.shutdown()
    except Exception as e:
        logger.error(f"Server failed: {e}")
        raise
    finally:
        logger.info("Server shutdown complete")

def run_stdio():
    """Run Excel MCP server in stdio mode."""
    # No need to assign EXCEL_FILES_PATH in stdio mode

    try:
        logger.info("Starting Excel MCP server with stdio transport")
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed: {e}")
        raise
    finally:
        logger.info("Server shutdown complete")