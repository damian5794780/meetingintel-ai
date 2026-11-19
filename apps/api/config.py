import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')


@dataclass
class Settings:
    tavily_key: str = ''
    llm_key: str = ''
    llm_url: str = 'https://api.openai.com/v1'
    llm_model: str = 'gpt-4.1-mini'
    llm_output_mode: str = 'json_schema'
    database_path: str = str(ROOT / 'data/meetingintel.db')
    web_origin: str = 'http://localhost:3000'
    max_active: int = 3
    job_timeout: int = 120
    input_rate: float | None = None
    output_rate: float | None = None

    @property
    def live_ready(self) -> bool:
        return bool(self.tavily_key and self.llm_key)

    @classmethod
    def from_env(cls):
        return cls(
            tavily_key=os.getenv('TAVILY_API_KEY', ''), llm_key=os.getenv('LLM_API_KEY', ''),
            llm_url=os.getenv('LLM_BASE_URL', cls.llm_url).rstrip('/'),
            llm_model=os.getenv('LLM_MODEL', cls.llm_model),
            llm_output_mode=os.getenv('LLM_OUTPUT_MODE', cls.llm_output_mode),
            database_path=os.getenv('DATABASE_PATH', cls.database_path),
            web_origin=os.getenv('WEB_ORIGIN', cls.web_origin),
            max_active=max(1, int(os.getenv('MAX_ACTIVE_JOBS', '3'))),
            job_timeout=max(10, int(os.getenv('JOB_TIMEOUT_SECONDS', '120'))),
            input_rate=float(os.environ['LLM_INPUT_USD_PER_MILLION']) if os.getenv('LLM_INPUT_USD_PER_MILLION') else None,
            output_rate=float(os.environ['LLM_OUTPUT_USD_PER_MILLION']) if os.getenv('LLM_OUTPUT_USD_PER_MILLION') else None,
        )
