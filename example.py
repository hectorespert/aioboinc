import asyncio

from aioboinc import BOINCAuthError, init_rpc_client
from aioboinc.rpc_client import Mode

IP_BOINC = "127.0.0.1"
PASSWORD_BOINC = "example_password"


async def main():
    # Every error is a BOINCError. A host that cannot be reached, or that stops answering, raises
    # BOINCConnectionError; one that takes more than 30 seconds to answer, its subclass
    # BOINCTimeoutError. Pass timeout= to change it, or timeout=None to wait forever. A request
    # that BOINC answers with an error, such as a task that does not exist, raises BOINCCommandError.
    rpc_client = await init_rpc_client(IP_BOINC, PASSWORD_BOINC)
    try:
        # Connecting does not authenticate. Do it before anything else: without it BOINC refuses
        # to change anything, and to answer queries from another host, with BOINCAuthError.
        try:
            await rpc_client.authorize()
        except BOINCAuthError:
            raise SystemExit("Wrong password") from None

        print(await rpc_client.get_cc_status())
        print(await rpc_client.get_project_status())

        # Get the last three messages
        c = await rpc_client.get_message_count()
        print(await rpc_client.get_messages(c - 3))

        # Get the tasks
        results = await rpc_client.get_results()
        print(results)

        # Suspend a task and resume it
        if results:
            task = (results[0]["project_url"], results[0]["name"])
            print(await rpc_client.suspend_result(*task))
            print(await rpc_client.resume_result(*task))

        # Stop computing for an hour, then go back to what was configured.
        # A duration of 0, the default, makes the change permanent.
        print(await rpc_client.set_run_mode(Mode.NEVER, 3600))
    finally:
        await rpc_client.close()


asyncio.run(main())
