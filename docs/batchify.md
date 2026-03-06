# batchify

The `batchify` function is the one and only entrypoint for the `batchling` library, everything starts from there.

It can be used either through the [Python SDK](./python-sdk.md){ data-preview } or [CLI](./cli.md){ data-preview } depending on your needs.

It comes with a bunch of parameters that you can customize to alter how batching is performed:

By default, provider batches use a `24h` completion window. You can request `1h`
through `batchify(completion_window="1h")` or the CLI when the active provider
supports it. Doubleword currently supports both `24h` and `1h`; other providers
raise an exception if `1h` is requested.

::: batchling.api.batchify
    options:
      separate_signature: true
      show_root_heading: true
      show_root_full_path: false
      show_source: true
      heading_level: 2
      docstring_style: numpy

## Next steps

Now that you have more information about the `batchify` function, you can:

- Learn to use it from the [Python SDK](./python-sdk.md) or the [CLI](./cli.md)

- See on which [Frameworks](./frameworks.md) & [Providers](./providers.md) it can be used

- Learn more about [advanced features](./advanced-features.md)
