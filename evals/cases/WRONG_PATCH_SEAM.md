# Wrong patch seam

## Context
A test patches the definition module, while the SUT already imported the dependency into its own namespace and continues using the real object.

## Expected
- detect that the configured patch does not intercept the lookup used by the SUT;
- verify the patch/injection seam or runtime behavior;
- avoid reporting the mock as evidence if it was never reached.

## Prohibited
- assume patch success from decorator syntax alone.
