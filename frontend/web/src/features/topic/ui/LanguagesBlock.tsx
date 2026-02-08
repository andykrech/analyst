import { useEffect, useRef, useState } from 'react'
import ISO6391 from 'iso-639-1'
import { useTopicStore } from '@/app/store/topicStore'
import './LanguagesBlock.css'

const ALL_CODES = ISO6391.getAllCodes()

function getLabel(code: string) {
  const native = ISO6391.getNativeName(code)
  return `${native} (${code})`
}

export function LanguagesBlock() {
  const languages = useTopicStore((s) => s.data.theme.languages)
  const setPrimaryLanguage = useTopicStore((s) => s.setPrimaryLanguage)
  const addAdditionalLanguage = useTopicStore((s) => s.addAdditionalLanguage)
  const removeAdditionalLanguage = useTopicStore((s) => s.removeAdditionalLanguage)
  const initDone = useRef(false)

  const primary = languages[0] ?? ''
  const additional = languages.slice(1)
  const [additionalSelect, setAdditionalSelect] = useState('')

  useEffect(() => {
    if (initDone.current || languages.length > 0) return
    initDone.current = true
    const navLang = navigator.language.split('-')[0]
    const code = ISO6391.validate(navLang) ? navLang : 'ru'
    setPrimaryLanguage(code)
  }, [languages.length, setPrimaryLanguage])

  const primaryOptions = ALL_CODES.filter(
    (code) => !additional.some((a) => a.toLowerCase() === code.toLowerCase())
  )

  const additionalOptions = ALL_CODES.filter(
    (code) =>
      code.toLowerCase() !== primary.toLowerCase() &&
      !additional.some((a) => a.toLowerCase() === code.toLowerCase())
  )

  return (
    <section className="languages-block">
      <label className="languages-block__label">Языки</label>

      <div className="languages-block__primary">
        <label className="languages-block__sublabel">Основной язык</label>
        <select
          className="languages-block__select"
          value={primary}
          onChange={(e) => setPrimaryLanguage(e.target.value)}
        >
          <option value="">—</option>
          {primaryOptions.map((code) => (
            <option key={code} value={code}>
              {getLabel(code)}
            </option>
          ))}
        </select>
      </div>

      <div className="languages-block__additional">
        <label className="languages-block__sublabel">Дополнительные языки</label>
        <div className="languages-block__add-row">
          <select
            className="languages-block__select languages-block__select--flex"
            value={additionalSelect}
            onChange={(e) => setAdditionalSelect(e.target.value)}
          >
            <option value="">Выберите язык</option>
            {additionalOptions.map((code) => (
              <option key={code} value={code}>
                {getLabel(code)}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="languages-block__btn-add"
            onClick={() => {
              if (additionalSelect) {
                addAdditionalLanguage(additionalSelect)
                setAdditionalSelect('')
              }
            }}
          >
            +
          </button>
        </div>
        <ul className="languages-block__list">
          {additional.map((code) => (
            <li key={code} className="languages-block__item">
              <span>{getLabel(code)}</span>
              <button
                type="button"
                className="languages-block__btn-remove"
                onClick={() => removeAdditionalLanguage(code)}
                aria-label={`Удалить ${code}`}
              >
                −
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
