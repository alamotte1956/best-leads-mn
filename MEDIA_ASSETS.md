# Local service illustrations and optimized images

Service pages now serve local WebP illustrations from `static/images/services/` rather than third-party Unsplash URLs. These images were generated with the built-in image-generation tool during the earlier landing-page work, inspected and resized for web delivery. They represent general situations, not actual customer projects or company staff.

| Routes | Illustration |
|---|---|
| Water damage, basement flooding, sewer backup, frozen pipes | Basement drying equipment |
| Storm/hail damage, emergency tarping | House with wind-damaged shingles and fallen branches |
| Roof repair, siding repair | Suburban home exterior and asphalt shingle roof |
| Mold remediation | Moisture staining and suspected mold on basement drywall |
| Fire/smoke damage | Kitchen affected by soot after a contained fire |

Related service categories share images. The photos do not prove the type, cause or extent of damage at any customer's property. Visible captions state they are AI-generated illustrations. All five service WebP files are under 240 KB at 1280 pixels wide.

The approved MN and USA PNG logos are preserved byte-for-byte. Lossless WebP renditions at 1086 × 362 pixels are provided through picture/source elements, with the original PNGs as fallbacks. The national illustrative hero retains its original PNG and offers an approximately 90 KB WebP alternative. Resizing/encoding changes delivery size, not logo content.

## Original generation prompts

Shared prefix: “Use case: photorealistic-natural. Asset type: wide website service hero photograph, 1536 by 1024 landscape composition. Create a photorealistic editorial illustrative photograph for a Minnesota restoration contractor connection website.”

- Water: A clean, unoccupied Minnesota residential basement with a portable industrial air mover and dehumidifier drying a small area of wet concrete floor following a leak. Realistic equipment, no flooding, daylight through a basement window.
- Fire: An unoccupied residential kitchen after a contained fire, with subtle soot on one wall above the stove and a few affected cabinets, no flames or active smoke. Natural window light, restrained and respectful.
- Mold: A close editorial view of a small patch of moisture staining and dark mold-like growth on exposed basement drywall near a window, no people or cleaning activity. Realistic building materials, natural daylight.
- Storm: A Minnesota suburban house after a windstorm, viewed from ground level, with a few missing asphalt shingles and small fallen branches on the lawn. Clear calm sky after rain, no people or emergency vehicles.
- Roofing: An attractive ordinary Minnesota suburban home with a charcoal asphalt shingle gable roof, crisp flashing and gutters, photographed from safe ground level in warm natural daylight. Roof is the clear visual subject, no workers or ladders.

Shared suffix: “Authentic materials, balanced understated colors, realistic scale, professional architectural photography, no text, no logos, no watermark, no collage. It must not look like a branded company's completed project.”

The existing national hero provenance remains in `static/images/restoration-professional-hero.provenance.txt`.
