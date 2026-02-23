import unittest
import inspect
from ilumi_sdk import IlumiSDK

class TestSDKStructure(unittest.TestCase):
    def test_sdk_methods_have_docstrings(self):
        """Verify that all public methods in IlumiSDK have docstrings."""
        sdk = IlumiSDK()
        public_methods = [m for m in dir(sdk) if not m.startswith("_")]
        
        for method_name in public_methods:
            method = getattr(sdk, method_name)
            if inspect.ismethod(method) or inspect.isfunction(method):
                self.assertIsNotNone(method.__doc__, f"Method {method_name} is missing a docstring.")
                self.assertGreater(len(method.__doc__.strip()), 10, f"Docstring for {method_name} is too short.")

    def test_sdk_methods_have_type_hints(self):
        """Verify that all public methods in IlumiSDK have type hints."""
        sdk = IlumiSDK()
        public_methods = [m for m in dir(sdk) if not m.startswith("_")]
        
        for method_name in public_methods:
            method = getattr(sdk, method_name)
            if inspect.ismethod(method) or inspect.isfunction(method):
                # Skip __init__ as it's often handled specially, but we added hints there too
                if method_name == "__init__":
                    continue
                
                hints = inspect.get_annotations(method)
                # We expect at least some hints for most methods (except maybe those with no args but we usually hint return)
                # This is a soft check to ensure we didn't forget them.
                self.assertGreater(len(hints), 0, f"Method {method_name} appears to be missing type hints.")

if __name__ == "__main__":
    unittest.main()
