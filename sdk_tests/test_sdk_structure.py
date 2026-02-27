import unittest
import inspect
import sys
import os
import importlib

# Ensure we can import the modules
sys.path.append(os.getcwd())

class TestSDKStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Explicitly import the two SDK versions
        # Disable shim for ilumi_sdk import if it's set in env
        old_val = os.environ.get("ILUMI_USE_BUMBLE")
        if "ILUMI_USE_BUMBLE" in os.environ:
            del os.environ["ILUMI_USE_BUMBLE"]
        
        # We need to bypass the sys.modules cache if it was already loaded with shim
        if "ilumi_sdk" in sys.modules:
            del sys.modules["ilumi_sdk"]
        
        import ilumi_sdk
        cls.IlumiSDK_bleak = ilumi_sdk.IlumiSDK
        
        import bumble_sdk
        cls.IlumiSDK_bumble = bumble_sdk.IlumiSDK
        cls.execute_on_targets_bumble = bumble_sdk.execute_on_targets
        
        # Restore env
        if old_val:
            os.environ["ILUMI_USE_BUMBLE"] = old_val

    def test_sdk_methods_have_docstrings(self):
        """Verify that all public methods in IlumiSDK (Bumble) have docstrings."""
        sdk = self.IlumiSDK_bumble()
        public_methods = [m for m in dir(sdk) if not m.startswith("_")]
        
        for method_name in public_methods:
            method = getattr(sdk, method_name)
            if inspect.ismethod(method) or inspect.isfunction(method):
                self.assertIsNotNone(method.__doc__, f"Method {method_name} is missing a docstring.")
                self.assertGreater(len(method.__doc__.strip()), 10, f"Docstring for {method_name} is too short.")

    def test_sdk_methods_have_type_hints(self):
        """Verify that all public methods in IlumiSDK (Bumble) have type hints."""
        sdk = self.IlumiSDK_bumble()
        public_methods = [m for m in dir(sdk) if not m.startswith("_")]
        
        for method_name in public_methods:
            method = getattr(sdk, method_name)
            if inspect.ismethod(method) or inspect.isfunction(method):
                if method_name == "__init__":
                    continue
                hints = inspect.get_annotations(method)
                self.assertGreater(len(hints), 0, f"Method {method_name} appears to be missing type hints.")

    def test_api_parity(self):
        """Verify 1:1 public API parity between Bleak-SDK and Bumble-SDK."""
        bleak_methods = {m for m in dir(self.IlumiSDK_bleak) if not m.startswith("_")}
        bumble_methods = {m for m in dir(self.IlumiSDK_bumble) if not m.startswith("_")}
        
        # Methods in Bleak but not in Bumble
        missing_in_bumble = bleak_methods - bumble_methods
        self.assertEqual(missing_in_bumble, set(), f"Methods in BleakSDK missing in BumbleSDK: {missing_in_bumble}")
        
        # Methods in Bumble but not in Bleak (extra methods are okay if they are logical extensions, 
        # but for a drop-in they should ideally match)
        extra_in_bumble = bumble_methods - bleak_methods
        # discover is now static/classmethod in bumble, might appear differently if not handled
        self.assertEqual(extra_in_bumble, set(), f"Extra public methods in BumbleSDK: {extra_in_bumble}")

    def test_method_signatures_match(self):
        """Verify that public method signatures match between both SDK versions."""
        public_methods = [m for m in dir(self.IlumiSDK_bleak) if not m.startswith("_")]
        
        for m_name in public_methods:
            bleak_method = getattr(self.IlumiSDK_bleak, m_name)
            bumble_method = getattr(self.IlumiSDK_bumble, m_name)
            
            if not (inspect.ismethod(bleak_method) or inspect.isfunction(bleak_method)):
                continue
            
            bleak_sig = inspect.signature(bleak_method)
            bumble_sig = inspect.signature(bumble_method)
            
            # Signature strings might differ in Type Hint representation slightly, 
            # but the parameters should match.
            if m_name == "discover":
                # Bumble version has an extra 'transport' param
                self.assertIn("timeout", bumble_sig.parameters)
                self.assertIn("transport", bumble_sig.parameters)
                continue

            self.assertEqual(len(bleak_sig.parameters), len(bumble_sig.parameters), 
                             f"Parameter count mismatch for {m_name}")
            
            for p_name in bleak_sig.parameters:
                self.assertIn(p_name, bumble_sig.parameters, f"Parameter {p_name} missing in Bumble's {m_name}")

if __name__ == "__main__":
    unittest.main()
