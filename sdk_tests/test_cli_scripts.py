import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os
import importlib
import json
import io
from contextlib import redirect_stdout

# Ensure we can import the scripts
sys.path.append(os.getcwd())

class TestCLIScripts(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Force Bumble mode for tests
        self.env_patcher = patch.dict(os.environ, {"ILUMI_USE_BUMBLE": "1"})
        self.env_patcher.start()
        
        # Mock config.resolve_targets with intelligent side effect
        def mock_resolve_logic(mac=None, name=None, group=None, all_bulbs=False, target_mac=None, target_name=None, target_group=None, target_all=False):
            # Handle both positional (from line 25 in on.py) and keyword (from line 34)
            # Normalizing arguments
            m = target_mac or mac
            n = target_name or name
            g = target_group or group
            a = target_all or all_bulbs
            
            if a: return ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"]
            if g: return ["AA:BB:CC:DD:EE:03", "AA:BB:CC:DD:EE:04"]
            if m and ":" in str(m): return [m] # MAC provided
            if n:
                if ":" in str(n): return [n] # It's a MAC
                return [f"MAC_FOR_{n.upper()}"]
            if m: return [m]
            return ["AA:BB:CC:DD:EE:01"]
            
        self.resolve_patcher = patch("config.resolve_targets", side_effect=mock_resolve_logic)
        self.mock_resolve = self.resolve_patcher.start()
        
        # Prepare SDK Mock
        self.sdk_instance = MagicMock()
        self.sdk_instance.__aenter__ = AsyncMock(return_value=self.sdk_instance)
        self.sdk_instance.__aexit__ = AsyncMock()
        self.sdk_instance.mac_address = "AA:BB:CC:DD:EE:01"
        self.sdk_instance.turn_on = AsyncMock()
        self.sdk_instance.turn_off = AsyncMock()
        self.sdk_instance.set_color = AsyncMock()
        self.sdk_instance.set_color_smooth = AsyncMock()
        self.sdk_instance.set_candle_mode = AsyncMock()
        
        # Patch execute_on_targets in each module namespace
        self.exec_patchers = []
        for mod_name in ["on", "off", "color", "whites"]:
            p = patch(f"{mod_name}.execute_on_targets", new_callable=AsyncMock)
            self.exec_patchers.append(p)

    async def asyncTearDown(self):
        self.env_patcher.stop()
        self.resolve_patcher.stop()
        for p in self.exec_patchers:
            try:
                p.stop()
            except:
                pass

    async def run_script_main(self, mod_name, args):
        # Clear module from cache to ensure fresh patch application if needed
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])
        mod = importlib.import_module(mod_name)
        
        # Re-apply patches to the newly loaded module
        with patch(f"{mod_name}.execute_on_targets", new_callable=AsyncMock) as mock_exec:
            with patch("sys.argv", [f"{mod_name}.py"] + args):
                # Suppress output
                f = io.StringIO()
                with redirect_stdout(f):
                    await mod.main()
            return mock_exec

    async def test_on_direct_mac(self):
        mock_exec = await self.run_script_main("on", ["--mac", "AA:BB:CC:DD:EE:01"])
        mock_exec.assert_called_once()
        targets, coro_func = mock_exec.call_args[0]
        self.assertEqual(targets, ["AA:BB:CC:DD:EE:01"])
        
        # Test the injected behavior
        await coro_func(self.sdk_instance)
        self.sdk_instance.turn_on.assert_called_with(transit=1000)

    async def test_off_group_mesh(self):
        # group "Living Room" resolves to ["AA:BB:CC:DD:EE:03", "AA:BB:CC:DD:EE:04"]
        mock_exec = await self.run_script_main("off", ["--group", "Living Room", "--mesh", "--proxy", "AA:BB:CC:DD:EE:01"])
        
        mock_exec.assert_called_once()
        targets, coro_func = mock_exec.call_args[0]
        # Mesh connects to proxy
        self.assertEqual(targets, ["AA:BB:CC:DD:EE:01"])
        
        with patch("asyncio.sleep", AsyncMock()):
            await coro_func(self.sdk_instance)
        
        # Should call turn_off with mesh targets
        self.sdk_instance.turn_off.assert_called_with(transit=1000, targets=["AA:BB:CC:DD:EE:03", "AA:BB:CC:DD:EE:04"])

    async def test_color_stream(self):
        # all resolves to ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"]
        # Stream mode does not use execute_on_targets, it handles it internally
        # We patch ilumi_sdk.IlumiSDK which is what the script imports
        
        with patch("ilumi_sdk.IlumiSDK") as mock_sdk_class:
            mock_sdk_class.return_value = self.sdk_instance
            with patch("sys.argv", ["color.py", "255", "0", "0", "--all", "--stream"]):
                with patch("bumble_sdk.shutdown_bumble", AsyncMock()):
                    f = io.StringIO()
                    with redirect_stdout(f):
                        import color
                        importlib.reload(color)
                        await color.main()
        
        # Verify it created SDKs for each target
        self.assertEqual(mock_sdk_class.call_count, 2)
        # Verify set_color_smooth was called (default fade for stream is 500ms)
        self.sdk_instance.set_color_smooth.assert_called_with(255, 0, 0, 0, 255, duration_ms=500)

    async def test_whites_profile(self):
        mock_exec = await self.run_script_main("whites", ["daylight", "200", "--mac", "AA:BB:CC:DD:EE:01", "--no-fade"])
        
        mock_exec.assert_called_once()
        targets, coro_func = mock_exec.call_args[0]
        await coro_func(self.sdk_instance)
        
        # Daylight profile is (0, 69, 83, 255)
        # --no-fade sets fade=0, which triggers set_color (instant) instead of set_color_smooth
        self.sdk_instance.set_color.assert_called_with(0, 69, 83, 255, 200)

    async def test_whites_candle_mesh(self):
        # Use --all to get multiple targets for mesh testing
        mock_exec = await self.run_script_main("whites", ["candle_light", "--all", "--mesh", "--proxy", "AA:BB:CC:DD:EE:01"])
        
        mock_exec.assert_called_once()
        targets, coro_func = mock_exec.call_args[0]
        self.assertEqual(targets, ["AA:BB:CC:DD:EE:01"]) # Proxy target
        
        with patch("asyncio.sleep", AsyncMock()):
            await coro_func(self.sdk_instance)
        
        # Candle light should use set_candle_mode with all targets
        self.sdk_instance.set_candle_mode.assert_called_with(255, 190, 0, 29, 255, targets=["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"])

    async def test_on_name_mesh(self):
        # proxy "AA:BB:CC:DD:EE:01" resolves to "AA:BB:CC:DD:EE:01" (keyword arg target_mac)
        # name "Bulb2" resolves to "MAC_FOR_BULB2" (positional arg name)
        mock_exec = await self.run_script_main("on", ["--name", "Bulb2", "--mesh", "--proxy", "AA:BB:CC:DD:EE:01"])
        
        mock_exec.assert_called_once()
        targets, coro_func = mock_exec.call_args[0]
        self.assertEqual(targets, ["AA:BB:CC:DD:EE:01"]) # Proxy target
        
        with patch("asyncio.sleep", AsyncMock()):
            await coro_func(self.sdk_instance)
        
        self.sdk_instance.turn_on.assert_called_with(transit=1000, targets=["MAC_FOR_BULB2"])

    async def test_off_all_stream(self):
        # all resolves to ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"]
        import off
        with patch("ilumi_sdk.IlumiSDK") as mock_sdk_class:
            mock_sdk_class.return_value = self.sdk_instance
            with patch("sys.argv", ["off.py", "--all", "--stream"]):
                with patch("bumble_sdk.shutdown_bumble", AsyncMock()):
                    f = io.StringIO()
                    with redirect_stdout(f):
                        importlib.reload(off)
                        await off.main()
        
        self.assertEqual(mock_sdk_class.call_count, 2)
        self.sdk_instance.turn_off.assert_called_with(transit=1000)

    async def test_color_group_direct(self):
        # group Kitchen resolves to ["AA:BB:CC:DD:EE:03", "AA:BB:CC:DD:EE:04"]
        mock_exec = await self.run_script_main("color", ["0", "255", "0", "--group", "Kitchen"])
        
        mock_exec.assert_called_once()
        targets, coro_func = mock_exec.call_args[0]
        self.assertEqual(targets, ["AA:BB:CC:DD:EE:03", "AA:BB:CC:DD:EE:04"])
        
        await coro_func(self.sdk_instance)
        # Default fade for sequential/direct with multiple bulbs is 0
        self.sdk_instance.set_color.assert_called_with(0, 255, 0, 0, 255)

if __name__ == "__main__":
    unittest.main()
