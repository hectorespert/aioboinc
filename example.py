import asyncio

from aioboinc import init_rpc_client
from aioboinc.rpc_client import Mode

IP_BOINC = "127.0.0.1"
PASSWORD_BOINC = "example_password"


async def main():
    rpc_client = await init_rpc_client(IP_BOINC, PASSWORD_BOINC)
    try:
        # Connecting does not authenticate. Do it before anything else and check the answer:
        # without it BOINC refuses to change anything and gives incomplete answers to queries.
        if not await rpc_client.authorize():
            raise SystemExit("Wrong password")

        print(await rpc_client.get_cc_status())
        print(await rpc_client.get_project_status())

        # Get the last three messages
        c = await rpc_client.get_message_count()
        print(await rpc_client.get_messages(c - 3))

        # Get the tasks. With no tasks this is the string "\n" rather than an empty list.
        results = await rpc_client.get_results()
        print(results)

        # Suspend a task and resume it
        if isinstance(results, list) and results:
            task = (results[0]["project_url"], results[0]["name"])
            print(await rpc_client.suspend_result(*task))
            print(await rpc_client.resume_result(*task))

        # Stop computing for an hour, then go back to what was configured.
        # A duration of 0, the default, makes the change permanent.
        print(await rpc_client.set_run_mode(Mode.NEVER, 3600))
    finally:
        await rpc_client.close()


asyncio.run(main())
