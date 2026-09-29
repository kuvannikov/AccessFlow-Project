export type Names = { first_name: string; last_name: string }

export function createSlugSuggestion(
  fetchSlug: (names: Names) => Promise<string>,
  onSuggestion: (names: Names, slug: string) => void,
  onFailure: (error: unknown) => void,
  onSettled: () => void,
) {
  let revision = 0
  return {
    invalidate() { revision += 1 },
    async suggest(names: Names) {
      const current = ++revision
      try {
        const slug = await fetchSlug(names)
        if (revision === current) onSuggestion(names, slug)
      } catch (error) {
        if (revision === current) onFailure(error)
      } finally {
        if (revision === current) onSettled()
      }
    },
  }
}
