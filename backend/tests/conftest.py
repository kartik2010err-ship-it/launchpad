import os

# The suite registers and signs in far more often than a real client would.
# Rate limiting gets its own tests with a tight limit; everywhere else it must
# not make results depend on test order.
os.environ.setdefault("AUTH_RATE_LIMIT", "10000")
