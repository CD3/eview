import pytest
from pylasercalc.ui import LaserCalcApp


@pytest.mark.asyncio
async def test_start_app():
    app = EviewApp()

    async with app.run_test() as pilot:
        await pilot.press("right")
        await pilot.press("right")
        await pilot.press("right")
