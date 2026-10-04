# MAE Method Figure

- **Destination:** a research-method figure showcased in the bilingual README.
- **Source:** He et al., *Masked Autoencoders Are Scalable Vision Learners*, CVPR 2022, Section 3, pp. 16002-16003.
- **Core message:** asymmetric reconstruction training sends only visible patches through the encoder, introduces mask tokens afterward, and supervises missing pixels.
- **Visual anchor:** one recognizable bicycle image, consistently divided, masked, and reconstructed.
- **Topology:** image -> patches -> random selection -> visible embeddings with positions -> ViT encoder -> encoded features -> restore positions with shared mask tokens -> decoder positional embeddings -> lightweight decoder -> pixel prediction.
- **Supervision branch:** original masked patch targets and predicted masked pixels -> MSE. Visible pixels do not contribute.
- **Scope:** pre-training only; downstream encoder reuse is explained in the notes rather than a second diagram strip.
- **Encoding:** blue visible features, coral mask tokens, green reconstruction/loss. Labels and spatial indices also carry the distinction.
- **Illustrative choices:** 4 x 4 patch layout; visible indices 3, 6, 12, 13; original bicycle scene. These depict data flow, not measured reconstruction quality.
- **Formats:** saved 4K Image API outputs, a locally composed 4800 x 1920 PNG, and bilingual process GIFs.

## Layout

```text
Original -> 75% masking -> four crops -> encoder -> four latents
                                                        |
                              learned M x12 ------------+-> restore + positions
                                                                  |
                                                               decoder -> pixels
                                                                             |
Original masked targets ---------------------------------------------------- MSE
```

The diagram uses open aligned representations and a subordinate loss branch. Photo patches carry visual detail; operators carry short labels. The wider 5:2 composition places input, sampling, visible patches, encoding, token restoration, and decoding on one horizontal reading line. The shared mask vector sits directly above its append operation. The original paper establishes the computation but its figure artwork is not reused.

## Render Review

The final composition preserves four visible crops, four indexed encoded features, twelve copies of the shared mask vector, the full decoder input, and masked-only pixel loss. Local layout replaces the generated connections with exact ports: sampling stays between the input and visible grid, collected crops feed projection, encoded features and M enter the append operation, and all three supervision inputs reach the loss. Operator labels use explicit line breaks and internal padding; the two long operator labels have at least 24 px padding.

The renderer reuses the generated photographic patches and loss formula, normalizes patch labels, and reflows the representations without another provider request. The method prediction remains schematic. Code and input artwork are listed in the manifest.
