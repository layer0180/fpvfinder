/**
 * Guides (Ratgeber): one Markdown file per article and language.
 *
 *   src/content/guides/de/<slug>.md   -> /ratgeber/<slug>
 *   src/content/guides/en/<slug>.md   -> /en/guides/<slug>
 *
 * `translation` pairs the two language versions of an article (same value in
 * both files) - that is what hreflang and the language switch use.
 *
 * Legal statements in these files must cite a primary source in `sources`
 * and say when they were checked (`updated`). A wrong distance in a guide
 * about where you may fly does more harm than no guide.
 */
import { defineCollection } from 'astro:content'
import { glob } from 'astro/loaders'
import { z } from 'astro/zod'

const guides = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/guides' }),
  schema: z.object({
    title: z.string().max(70),
    description: z.string().min(70).max(170),
    h1: z.string(),
    lang: z.enum(['de', 'en']),
    slug: z.string().regex(/^[a-z0-9-]+$/),
    translation: z.string(),
    order: z.number(),
    /** Date the content - especially the legal parts - was last checked. */
    updated: z.coerce.date(),
    sources: z.array(z.object({ title: z.string(), url: z.url() })).default([]),
  }),
})

export const collections = { guides }
