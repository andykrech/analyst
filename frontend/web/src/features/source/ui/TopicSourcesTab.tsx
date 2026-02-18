import { useEffect, useMemo } from 'react'
import { useTopicStore } from '@/app/store/topicStore'
import { normalizeDomain } from '@/features/source/utils/normalizeDomain'
import { SourcesList } from './components/SourcesList'
import { SourceEditorModal } from './components/SourceEditorModal'
import './TopicSourcesTab.css'

interface TopicSourcesTabProps {
  themeId: string
}

export function TopicSourcesTab({ themeId }: TopicSourcesTabProps) {
  const siteSources = useTopicStore((s) => s.data.siteSources)
  const sourcesRecommend = useTopicStore((s) => s.sourcesRecommend)
  const theme = useTopicStore((s) => s.data.theme)
  const loadSources = useTopicStore((s) => s.loadSources)
  const openCreateSource = useTopicStore((s) => s.openCreateSource)
  const openEditSource = useTopicStore((s) => s.openEditSource)
  const closeSourceEditor = useTopicStore((s) => s.closeSourceEditor)
  const setSourceEditorField = useTopicStore((s) => s.setSourceEditorField)
  const createSourceFromEditor = useTopicStore((s) => s.createSourceFromEditor)
  const saveSourceEditor = useTopicStore((s) => s.saveSourceEditor)
  const muteSource = useTopicStore((s) => s.muteSource)
  const updateSourceModeStatus = useTopicStore((s) => s.updateSourceModeStatus)
  const clearSiteSourcesError = useTopicStore((s) => s.clearSiteSourcesError)
  const recommendSources = useTopicStore((s) => s.recommendSources)
  const clearSourcesRecommendError = useTopicStore((s) => s.clearSourcesRecommendError)
  const addRecommendedSource = useTopicStore((s) => s.addRecommendedSource)

  useEffect(() => {
    if (themeId) {
      loadSources()
    }
  }, [themeId, loadSources])

  const items = siteSources.order
    .map((id) => siteSources.itemsById[id])
    .filter((dto): dto is NonNullable<typeof dto> => Boolean(dto) && dto.status !== 'muted')

  const existingDomains = useMemo(() => {
    const set = new Set<string>()
    for (const dto of Object.values(siteSources.itemsById)) {
      if (dto.status === 'muted') continue
      const n = normalizeDomain(dto.site.domain)
      if (n) set.add(n)
    }
    return set
  }, [siteSources.itemsById])

  const canRecommend =
    (theme.title?.trim() ?? '').length > 0 || (theme.description?.trim() ?? '').length > 0

  const editor = siteSources.editor

  return (
    <div className="topic-sources-tab">
      {siteSources.error && (
        <div className="topic-sources-tab__error">
          {siteSources.error}
          <button
            type="button"
            onClick={clearSiteSourcesError}
            aria-label="Скрыть"
          >
            ×
          </button>
        </div>
      )}

      {sourcesRecommend.error && (
        <div className="topic-sources-tab__error">
          {sourcesRecommend.error}
          <button
            type="button"
            onClick={clearSourcesRecommendError}
            aria-label="Скрыть"
          >
            ×
          </button>
        </div>
      )}

      <div className="topic-sources-tab__layout">
        <aside className="topic-sources-tab__list-panel">
          <div className="topic-sources-tab__actions">
            <button
              type="button"
              className="topic-sources-tab__add-btn"
              onClick={openCreateSource}
            >
              Добавить источник
            </button>
            <button
              type="button"
              className="topic-sources-tab__suggest-btn"
              onClick={() => recommendSources()}
              disabled={sourcesRecommend.isLoading || !canRecommend}
            >
              {sourcesRecommend.isLoading
                ? 'Загрузка…'
                : 'Рекомендовать источники'}
            </button>
          </div>
          {siteSources.isLoading ? (
            <p className="topic-sources-tab__loading">Загрузка…</p>
          ) : (
            <SourcesList
              items={items}
              onEdit={openEditSource}
              onDelete={muteSource}
              onModeChange={(themeSiteId, mode) =>
                updateSourceModeStatus(themeSiteId, { mode })
              }
              onStatusChange={(themeSiteId, status) =>
                updateSourceModeStatus(themeSiteId, { status })
              }
            />
          )}

          {sourcesRecommend.lastResult && sourcesRecommend.lastResult.length > 0 && (
            <div className="topic-sources-tab__recommendations">
              <h3 className="topic-sources-tab__recommendations-title">
                Рекомендованные источники
              </h3>
              <ul className="topic-sources-tab__recommendations-list">
                {sourcesRecommend.lastResult.map((item) => {
                  const norm = normalizeDomain(item.domain)
                  const alreadyAdded = norm ? existingDomains.has(norm) : false
                  return (
                    <li
                      key={item.domain}
                      className="topic-sources-tab__recommendation-item"
                    >
                      <div className="topic-sources-tab__recommendation-content">
                        <span className="topic-sources-tab__recommendation-domain">
                          {item.display_name || item.domain}
                        </span>
                        {item.display_name && (
                          <span className="topic-sources-tab__recommendation-domain-raw">
                            {item.domain}
                          </span>
                        )}
                        {item.reason && (
                          <span className="topic-sources-tab__recommendation-reason">
                            {item.reason}
                          </span>
                        )}
                      </div>
                      {alreadyAdded ? (
                        <span className="topic-sources-tab__recommendation-badge">
                          Уже добавлен
                        </span>
                      ) : (
                        <button
                          type="button"
                          className="topic-sources-tab__recommendation-add"
                          onClick={() => addRecommendedSource(item)}
                        >
                          Добавить
                        </button>
                      )}
                    </li>
                  )
                })}
              </ul>
            </div>
          )}
        </aside>
      </div>

      {editor.isOpen && (
        <SourceEditorModal
          mode={editor.mode}
          domain={editor.form.domain}
          domainReadOnly={editor.mode === 'edit'}
          modeValue={editor.form.mode}
          statusValue={editor.form.status}
          displayName={editor.form.display_name}
          description={editor.form.description}
          homepageUrl={editor.form.homepage_url}
          trustScore={editor.form.trust_score}
          qualityTier={editor.form.quality_tier}
          error={siteSources.error}
          onDomainChange={(v) => setSourceEditorField('domain', v)}
          onModeChange={(v) => setSourceEditorField('mode', v)}
          onStatusChange={(v) => setSourceEditorField('status', v)}
          onDisplayNameChange={(v) => setSourceEditorField('display_name', v)}
          onDescriptionChange={(v) => setSourceEditorField('description', v)}
          onHomepageUrlChange={(v) => setSourceEditorField('homepage_url', v)}
          onTrustScoreChange={(v) => setSourceEditorField('trust_score', v)}
          onQualityTierChange={(v) => setSourceEditorField('quality_tier', v)}
          onSave={() =>
            editor.mode === 'create'
              ? createSourceFromEditor()
              : saveSourceEditor()
          }
          onCancel={closeSourceEditor}
          onClearError={clearSiteSourcesError}
        />
      )}
    </div>
  )
}
