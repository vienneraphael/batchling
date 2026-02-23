<!-- markdownlint-disable-file MD041 MD001 -->
## XAI client compatibility

The XAI provider is not made available through the base client but through an OpenAI client with modified `base_url`.

This is due to XAI heavy reliance on gRPC architecture within its client over REST-based requests, making it harder to intercept requests.
