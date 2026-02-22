# Quickstart

batchling is a powerful python library that lets you transform any async GenAI workflow to batched inference, saving you money for workloads that can complete asynchronously (up to 24 hours).
You typically want to use batched inference when running any process that does not require immediate response and can wait at most 24 hours (most jobs are completed in a few hours).

## Example use-cases

The range of use-cases you can tackle effortlessly with batchling is extremely wide, here are a few examples:

- Embedding text chunks for your RAG application overnight
- Running large-scale classification with your favourite GenAI provider and/or framework
- Run any GenAI evaluation pipeline
- Generate huge volume of synthtetic data at half the cost
- Transcribe or translate hours of audio in bulk

Things you might not want to run with batchling (yes, there are some..):

- User-facing applications e.g. chatbots, you typically want fast answers
- A whole agentic loop with tons of calls
- Full AI workflows with a lot of sequential calls (each additional step can add another asynchronous batch cycle, up to 24 hours at worst)

## Installation

batchling is available on PyPI as `batchling`, install using either `pip` or `uv`:

=== "uv"

    ```bash
    uv add batchling
    ```

=== "pip"

    ```bash
    pip install batchling
    ```

## Art Metadata Generation Example

batchling integrates smoothly with any async function doing GenAI calls or within a whole async script that you'd run with `asyncio`.

Let's try to generate metadata for famous pieces of art from the National Gallery of Arts.

For this example, we'll use the three following art pieces:

<div style="display: flex; gap: 12px; justify-content: space-between; flex-wrap: wrap;">
  <img src="../assets/images/quickstart/woman-striped-dress.png" alt="Portrait of a Woman in Striped Dress" style="width: 32%; min-width: 220px;" />
  <img src="../assets/images/quickstart/napoleon.png" alt="Portrait of a Napoleonic Officer in Dress Uniform" style="width: 32%; min-width: 220px;" />
  <img src="../assets/images/quickstart/self-portrait.png" alt="Self-Portrait with Palette" style="width: 32%; min-width: 220px;" />
</div>

For each art piece, we will generate the following metadata:

- author name
- name of the art piece
- period in which it was created
- movement to which it belongs
- material used to create the piece
- list of tags representing visual elements of the art piece
- short description about the background
- fun fact about it

Let's suppose we have an existing script `art_metadata.py` that uses the OpenAI client to make two parallel calls using `asyncio.gather`:

<!-- markdownlint-disable-next-line MD046 -->
```python
--8<-- "examples/art_metadata.py:quickstart"
```

=== "CLI"

    For you to switch this async execution to a batched inference one, you just have to run your script using the [`batchling` CLI](./cli.md) and targetting the generate function ran by `asyncio`:

    ```bash
    batchling main.py:enrich_art_images
    ```

=== "Python SDK"

    To selectively batchify certain pieces of your code execution, you can rely on the [`batchify`](./batchify.md) function, which exposes an async context manager.

    First, add this import at the top of your file:

    ```diff
    + from batchling import batchify
    ```

    Then, let's modify our async function `generate` to wrap the `asyncio.gather` call into the [`batchify`](./batchify.md) async context manager:

    ```diff
     async def enrich_art_images() -> None:
         """Run the OpenAI example."""
         tasks = await build_tasks()
    -    responses = await asyncio.gather(*tasks)
    +    with batchify():
    +        responses = await asyncio.gather(*tasks)
         for response in responses:
             print(response.output_parsed.model_dump_json(indent=2))
    ```

Output:

<div style="display: flex; gap: 16px; align-items: stretch; margin-bottom: 16px; flex-wrap: wrap;">
  <div style="flex: 1 1 240px; max-width: 33%; min-width: 220px; display: flex;">
    <img src="../assets/images/quickstart/woman-striped-dress.png" alt="Portrait of a Woman in Striped Dress" style="width: 100%; height: 100%; object-fit: cover;" />
  </div>
  <div style="flex: 2 1 420px; min-width: 320px; display: flex;">
    <pre style="margin: 0; width: 100%; height: 100%; overflow: auto;"><code class="language-json">{
  "author": "",
  "name": "Portrait of a Woman in Striped Dress",
  "period": "Early 20th century",
  "movement": "Post-Impressionism / Fauvism influence",
  "material": "Oil on canvas",
  "tags": [
    "portrait",
    "woman",
    "stripes",
    "bold color",
    "flower bouquet",
    "interior",
    "fauvism",
    "post-impressionism"
  ],
  "context": "A seated young woman in a striped red-and-blue blouse and a polka-dot blue skirt, holding flowers, set against a flat mint-green background. The brushwork and color treatment emphasize flat planes and expressive color typical of Post-Impressionist/Fauvist portraiture.",
  "fun_fact": "The composition and bold color palette resemble early 20th-century French modernist works; exact attribution is difficult from a single image."
}</code></pre>
  </div>
</div>

<div style="display: flex; gap: 16px; align-items: stretch; margin-bottom: 16px; flex-wrap: wrap;">
  <div style="flex: 1 1 240px; max-width: 33%; min-width: 220px; display: flex;">
    <img src="../assets/images/quickstart/napoleon.png" alt="Portrait of a Napoleonic Officer in Dress Uniform" style="width: 100%; height: 100%; object-fit: cover;" />
  </div>
  <div style="flex: 2 1 420px; min-width: 320px; display: flex;">
    <pre style="margin: 0; width: 100%; height: 100%; overflow: auto;"><code class="language-json">{
  "author": "",
  "name": "",
  "period": "Early 19th century (Napoleonic era)",
  "movement": "",
  "material": "Oil on canvas",
  "tags": [
    "portrait",
    "military",
    "uniform",
    "Napoleonic era",
    "European",
    "blue coat",
    "epaulettes",
    "medal",
    "sash"
  ],
  "context": "A formal portrait of a high-ranking military officer in full dress uniform, set in an ornate interior with classical furnishings, suggesting a studio or official setting typical of early 19th-century noble or military portraiture.",
  "fun_fact": "The subject wears a star medal and epaulettes common to high-ranking officers of Napoleonic Europe; the rich interior and ceremonial attire indicate status and prestige rather than battlefield activity."
}</code></pre>
  </div>
</div>

<div style="display: flex; gap: 16px; align-items: stretch; flex-wrap: wrap;">
  <div style="flex: 1 1 240px; max-width: 33%; min-width: 220px; display: flex;">
    <img src="../assets/images/quickstart/self-portrait.png" alt="Self-Portrait with Palette" style="width: 100%; height: 100%; object-fit: cover;" />
  </div>
  <div style="flex: 2 1 420px; min-width: 320px; display: flex;">
    <pre style="margin: 0; width: 100%; height: 100%; overflow: auto;"><code class="language-json">{
  "author": "Vincent van Gogh",
  "name": "Self-Portrait with Palette",
  "period": "1889",
  "movement": "Post-Impressionism",
  "material": "Oil on canvas",
  "tags": [
    "Self-portrait",
    "palette",
    "brushwork",
    "van Gogh",
    "Post-Impressionism",
    "blue background",
    "oil on canvas"
  ],
  "context": "A self-portrait painted by Vincent van Gogh during his stay at the Saint-Paul asylum in Saint-Rémy-de-Provence in 1889. The image shows van Gogh holding a palette, set against a swirling blue background that demonstrates his bold, expressive brushwork and distinctive color sense.",
  "fun_fact": "Van Gogh produced hundreds of self-portraits, using them to study color and emotion; this piece is notable for its cool blue tones contrasting with the warmer tones of his hair and beard."
}</code></pre>
  </div>
</div>

You can run the script and see for yourself, normally small batches like that should run under 5-10 minutes at most.

## Next Steps

Now that you've seen how `batchling` can be used and want to learn more about it, you can header over to the following sections of the documentation:

- [Learn how to control batching behavior through batchify parameters](./batchify.md)

- [Learn more about the Python SDK usage](./python-sdk.md)

- [Learn more about CLI usage](./cli.md)

- Learn about supported [Providers](./providers.md) & [Frameworks](./frameworks.md)

- [Browse batchling in-depth use-cases exploration](./use-cases.md)
