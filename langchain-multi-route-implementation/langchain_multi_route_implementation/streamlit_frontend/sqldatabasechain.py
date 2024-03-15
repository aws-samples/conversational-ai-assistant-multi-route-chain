from __future__ import annotations

"""Chain for interacting with SQL Database."""

"""
Modified implementation of LangChain SQL Database Chain 

The original LangChain implementation is an open-source project focused on providing
flexible and extensible chains for various language models. This modified version builds 
upon that foundation to enhance compatibility with Anthropic Claude.

For more details on the original implementation and its features, please refer to the following documentation:
- https://github.com/langchain-ai/langchain/
- https://github.com/langchain-ai/langchain/blob/master/libs/experimental/langchain_experimental/sql/base.py
- https://python.langchain.com/docs/use_cases/qa_structured/sql#quickstart
"""

import warnings
from typing import Any, Dict, List, Optional

from langchain.callbacks.manager import CallbackManagerForChainRun
from langchain.chains.base import Chain
from langchain.chains.llm import LLMChain
from langchain.chains.sql_database.prompt import DECIDER_PROMPT, PROMPT, SQL_PROMPTS
from langchain.prompts.prompt import PromptTemplate
from langchain.schema import BasePromptTemplate
from langchain.schema.language_model import BaseLanguageModel
from langchain.tools.sql_database.prompt import QUERY_CHECKER
from langchain.utilities.sql_database import SQLDatabase
import re
from langchain_experimental.pydantic_v1 import Extra, Field, root_validator


INTERMEDIATE_STEPS_KEY = "intermediate_steps"


def clean_docstring(doc: Optional[str]) -> Optional[str]:
    """Remove XML tags from a given docstring."""
    if doc:
        return re.sub(r'<[^>]*>', '', doc).strip()
    return None


prompt_update = """
Given an input question input with "Answer:" like in <Example></Example>, make sure you: first, extract data from SQLResult. Then, interpret the data in context with the initial question. And last, Formulate a human-readable answer with no SQL. NO <SQL></SQL> Syntax in final Answer, Just the final answer in plain English like <Answer></Answer>
                <Example>
                Question: Give me all the shipments to the United States that originated from Taiwan
                SQLQuery: 
                SELECT *
                FROM "AwsDataCatalog"."coupa_demo_db_simple"."coupa_simple_cleaned"
                where origin_country = 'TW'
                	and dest_country = 'US'
                SQLResult: [(1007, 197.5, 248.0, 99.0)] 
                <Answer>
                The below is a list for all shipments to the US that originated from Taiwan
                </Answer>
                </Example>
                """


class SQLDatabaseChain(Chain):
    """Chain for interacting with SQL Database.

    Example:
        .. code-block:: python

            from langchain_experimental.sql import SQLDatabaseChain
            from langchain.llms import OpenAI, SQLDatabase
            db = SQLDatabase(...)
            db_chain = SQLDatabaseChain.from_llm(OpenAI(), db)

    *Security note*: Make sure that the database connection uses credentials
        that are narrowly-scoped to only include the permissions this chain needs.
        Failure to do so may result in data corruption or loss, since this chain may
        attempt commands like `DROP TABLE` or `INSERT` if appropriately prompted.
        The best way to guard against such negative outcomes is to (as appropriate)
        limit the permissions granted to the credentials used with this chain.
        This issue shows an example negative outcome if these steps are not taken:
        https://github.com/langchain-ai/langchain/issues/5923
    """

    llm_chain: LLMChain
    llm: Optional[BaseLanguageModel] = None
    """[Deprecated] LLM wrapper to use."""
    database: SQLDatabase = Field(exclude=True)
    """SQL Database to connect to."""
    prompt: Optional[BasePromptTemplate] = None
    """[Deprecated] Prompt to use to translate natural language to SQL."""
    top_k: int = 5
    """Number of results to return from the query"""
    input_key: str = "query"  #: :meta private:
    output_key: str = "result"  #: :meta private:
    return_sql: bool = False
    """Will return sql-command directly without executing it"""
    return_intermediate_steps: bool = False
    """Whether or not to return the intermediate steps along with the final answer."""
    return_direct: bool = False
    """Whether or not to return the result of querying the SQL table directly."""
    use_query_checker: bool = False
    """Whether or not the query checker tool should be used to attempt
    to fix the initial SQL from the LLM."""
    query_checker_prompt: Optional[BasePromptTemplate] = None
    """The prompt template that should be used by the query checker"""

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid
        arbitrary_types_allowed = True

    @root_validator(pre=True, allow_reuse=True)
    def raise_deprecation(cls, values: Dict) -> Dict:
        if "llm" in values:
            warnings.warn(
                "Directly instantiating an SQLDatabaseChain with an llm is deprecated. "
                "Please instantiate with llm_chain argument or using the from_llm "
                "class method."
            )
            if "llm_chain" not in values and values["llm"] is not None:
                database = values["database"]
                prompt = values.get("prompt") or SQL_PROMPTS.get(
                    database.dialect, PROMPT
                )
                values["llm_chain"] = LLMChain(
                    llm=values["llm"], prompt=prompt)
        return values

    @property
    def input_keys(self) -> List[str]:
        """Return the singular input key.

        :meta private:
        """
        return [self.input_key]

    @property
    def output_keys(self) -> List[str]:
        """Return the singular output key.

        :meta private:
        """
        if not self.return_intermediate_steps:
            return [self.output_key]
        else:
            return [self.output_key, INTERMEDIATE_STEPS_KEY]

    def _call(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, Any]:
        _run_manager = run_manager or CallbackManagerForChainRun.get_noop_manager()
        input_text = f"{inputs[self.input_key]}\nSQLQuery:"
        _run_manager.on_text(input_text, verbose=self.verbose)
        # If not present, then defaults to None which is all tables.
        table_names_to_use = inputs.get("table_names_to_use")
        table_info = self.database.get_table_info(
            table_names=table_names_to_use)
        llm_inputs = {
            "input": input_text,
            "top_k": str(self.top_k),
            "dialect": self.database.dialect,
            "table_info": table_info,
            "stop": ["\nSQLResult:"],
        }
        if self.memory is not None:
            for k in self.memory.memory_variables:
                llm_inputs[k] = inputs[k]
        intermediate_steps: List = []
        try:
            # input: sql generation
            intermediate_steps.append(llm_inputs.copy())
            sql_cmd = self.llm_chain.predict(
                callbacks=_run_manager.get_child(),
                **llm_inputs,
            ).strip()
            sql_cmd = clean_docstring(sql_cmd)
            if self.return_sql:
                return {self.output_key: sql_cmd}
            if not self.use_query_checker:
                _run_manager.on_text(
                    sql_cmd, color="green", verbose=self.verbose)
                intermediate_steps.append(
                    sql_cmd
                )  # output: sql generation (no checker)
                intermediate_steps.append(
                    {"sql_cmd": sql_cmd})  # input: sql exec
                result = self.database.run(sql_cmd)
                intermediate_steps.append(str(result))  # output: sql exec
            else:
                query_checker_prompt = self.query_checker_prompt or PromptTemplate(
                    template=QUERY_CHECKER, input_variables=[
                        "query", "dialect"]
                )
                query_checker_chain = LLMChain(
                    llm=self.llm_chain.llm, prompt=query_checker_prompt
                )
                query_checker_inputs = {
                    "query": sql_cmd,
                    "dialect": self.database.dialect,
                }
                checked_sql_command: str = query_checker_chain.predict(
                    callbacks=_run_manager.get_child(), **query_checker_inputs
                ).strip()
                checked_sql_command = clean_docstring(checked_sql_command)
                intermediate_steps.append(
                    checked_sql_command
                )  # output: sql generation (checker)
                _run_manager.on_text(
                    checked_sql_command, color="green", verbose=self.verbose
                )
                intermediate_steps.append(
                    {"sql_cmd": checked_sql_command}
                )  # input: sql exec
                result = self.database.run(checked_sql_command)
                intermediate_steps.append(str(result))  # output: sql exec
                sql_cmd = checked_sql_command

            # _run_manager.on_text("\nSQLResult: ", verbose=self.verbose)
            # _run_manager.on_text(result, color="yellow", verbose=self.verbose)
            _run_manager.on_text("\nSQLResult: ", verbose=self.verbose)
            cleaned_result = clean_docstring(result)
            _run_manager.on_text(
                cleaned_result, color="yellow", verbose=self.verbose)

            # If return direct, we just set the final result equal to
            # the result of the sql query result, otherwise try to get a human readable
            # final answer
        #     if self.return_direct:
        #         final_result = result
        #     else:
        #         _run_manager.on_text("\nAnswer:", verbose=self.verbose)
        #         input_text += f"{sql_cmd}\nSQLResult: {result}\nAnswer:"
        #         llm_inputs["input"] = input_text
        #         intermediate_steps.append(llm_inputs.copy())  # input: final answer
        #         final_result = self.llm_chain.predict(
        #             callbacks=_run_manager.get_child(),
        #             **llm_inputs,
        #         ).strip()
        #         intermediate_steps.append(final_result)  # output: final answer
        #         _run_manager.on_text(final_result, color="green", verbose=self.verbose)
        #     chain_result: Dict[str, Any] = {self.output_key: final_result}
        #     if self.return_intermediate_steps:
        #         chain_result[INTERMEDIATE_STEPS_KEY] = intermediate_steps
        #     return chain_result
        # except Exception as exc:
        #     # Append intermediate steps to exception, to aid in logging and later
        #     # improvement of few shot prompt seeds
        #     exc.intermediate_steps = intermediate_steps  # type: ignore
        #     raise exc
            if self.return_direct:
                final_result = clean_docstring(result)
            else:
                _run_manager.on_text("\nAnswer:", verbose=self.verbose)
                cleaned_result = clean_docstring(result)
                sql_cmd = clean_docstring(sql_cmd)
                input_text += f"SQL:{sql_cmd}\nSQLResult: {cleaned_result}\nAnswer:"
                llm_inputs["input"] = input_text
                intermediate_steps.append(
                    llm_inputs.copy())  # input: final answer
                final_result = self.llm_chain.predict(
                    callbacks=_run_manager.get_child(),
                    **llm_inputs,
                ).strip()
                intermediate_steps.append(final_result)  # output: final answer
                _run_manager.on_text(
                    final_result, color="green", verbose=self.verbose)
                final_result = clean_docstring(final_result)

            chain_result: Dict[str, Any] = {self.output_key: final_result}
            if self.return_intermediate_steps:
                chain_result[INTERMEDIATE_STEPS_KEY] = intermediate_steps
            return chain_result

        except Exception as exc:
            # Append intermediate steps to exception, to aid in logging and later
            # improvement of few shot prompt seeds
            exc.intermediate_steps = intermediate_steps  # type: ignore
            raise exc

    @property
    def _chain_type(self) -> str:
        return "sql_database_chain"

    @classmethod
    def from_llm(
        cls,
        llm: BaseLanguageModel,
        db: SQLDatabase,
        prompt: Optional[BasePromptTemplate] = None,
        **kwargs: Any,
    ) -> SQLDatabaseChain:
        """Create a SQLDatabaseChain from an LLM and a database connection.

        *Security note*: Make sure that the database connection uses credentials
            that are narrowly-scoped to only include the permissions this chain needs.
            Failure to do so may result in data corruption or loss, since this chain may
            attempt commands like `DROP TABLE` or `INSERT` if appropriately prompted.
            The best way to guard against such negative outcomes is to (as appropriate)
            limit the permissions granted to the credentials used with this chain.
            This issue shows an example negative outcome if these steps are not taken:
            https://github.com/langchain-ai/langchain/issues/5923
        """
        prompt = prompt or SQL_PROMPTS.get(db.dialect, PROMPT)
        llm_chain = LLMChain(llm=llm, prompt=prompt)
        return cls(llm_chain=llm_chain, database=db, **kwargs)


SQLDatabaseChain.__doc__ = clean_docstring(SQLDatabaseChain.__doc__)
