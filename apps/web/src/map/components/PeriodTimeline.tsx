import { useEffect, useEffectEvent, useRef, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { ChoiceSelector } from '../../components/custom/ChoiceSelector';
import type { MarketState } from '../../market/interfaces/market-state';
import { formatQuarter } from '../../market/lib/market-format';

const SPEEDS = [
  { code: '3600', title: '0,5×' },
  { code: '1800', title: '1×' },
  { code: '900', title: '2×' },
  { code: '450', title: '4×' },
];

export function PeriodTimeline({
  market,
  playing,
  setPlaying,
}: {
  market: MarketState;
  playing: boolean;
  setPlaying: Dispatch<SetStateAction<boolean>>;
}) {
  const periods = [...(market.quarters.data || [])]
    .reverse()
    .map((quarter) => quarter.period);
  const index = periods.indexOf(market.period);
  const available = market.enabled && market.codeValid && market.published;
  const nextPeriod = index >= 0 ? periods[index + 1] : undefined;
  const targetPeriod = nextPeriod || periods[0];
  const ready =
    market.communities.isSuccess &&
    market.marketers.isSuccess &&
    (!market.community || market.areaMarketers.isSuccess);
  const loadError =
    market.communities.isError ||
    market.marketers.isError ||
    (!!market.community && market.areaMarketers.isError);
  const hasAdvanced = useRef(false);
  const expectedPeriod = useRef(market.period);
  const observedPeriod = useRef(market.period);
  const [playbackError, setPlaybackError] = useState<string | null>(null);
  const [frameMs, setFrameMs] = useState('1800');
  const preload = useEffectEvent((period: string) => market.preloadPeriod(period));

  const advance = useEffectEvent((period: string) => {
    expectedPeriod.current = period;
    market.change({ period }, { replace: hasAdvanced.current });
    hasAdvanced.current = true;
    if (period === periods.at(-1)) setPlaying(false);
  });

  useEffect(() => {
    if (market.period === observedPeriod.current) return;
    observedPeriod.current = market.period;
    if (playing && market.period !== expectedPeriod.current) setPlaying(false);
  }, [playing, market.period, setPlaying]);

  useEffect(() => {
    if (!playing) return;
    if (!available || loadError || !targetPeriod) {
      setPlaying(false);
      return;
    }
    if (!ready) return;
    let active = true;
    let timer = 0;
    const frame = new Promise<void>((resolve) => {
      timer = window.setTimeout(resolve, Number(frameMs));
    });
    void Promise.all([preload(targetPeriod), frame])
      .then(() => {
        if (!active) return;
        advance(targetPeriod);
      })
      .catch(() => {
        if (!active) return;
        setPlaybackError(targetPeriod);
        setPlaying(false);
      });
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [
    playing,
    available,
    loadError,
    ready,
    targetPeriod,
    frameMs,
    market.marketer,
    market.community,
    setPlaying,
  ]);

  function select(period: string) {
    setPlaying(false);
    hasAdvanced.current = false;
    expectedPeriod.current = period;
    setPlaybackError(null);
    market.change({ period });
  }

  function togglePlayback() {
    if (playing) {
      setPlaying(false);
      return;
    }
    hasAdvanced.current = false;
    expectedPeriod.current = market.period;
    setPlaybackError(null);
    // Starting at the latest observation preloads the first published quarter.
    // The first navigation remains in history; later frames replace only it.
    setPlaying(true);
  }

  return (
    <div className="period-timeline" role="group" aria-label="Línea temporal del mapa">
      <div className="period-timeline-heading">
        <strong>Recorrer trimestres</strong>
        <span>{market.published ? formatQuarter(market.period) : 'Sin periodo publicado'}</span>
      </div>
      <div className="period-timeline-controls">
        <button
          type="button"
          onClick={() => select(periods[index - 1])}
          disabled={!available || index <= 0}
          aria-label="Trimestre publicado anterior"
        >
          ‹
        </button>
        <button
          type="button"
          className="timeline-play"
          onClick={togglePlayback}
          disabled={!available || periods.length < 2 || loadError}
          aria-label={
            playing
              ? 'Pausar reproducción'
              : nextPeriod
                ? 'Reproducir trimestres'
                : 'Reproducir desde el primer trimestre'
          }
          aria-pressed={playing}
        >
          <span aria-hidden="true">{playing ? 'Ⅱ' : '▶'}</span>
          <span>{playing ? 'Pausar' : 'Reproducir'}</span>
        </button>
        <input
          type="range"
          min={0}
          max={Math.max(periods.length - 1, 0)}
          value={Math.max(index, 0)}
          onChange={(event) => select(periods[Number(event.target.value)])}
          disabled={!available || periods.length < 2}
          aria-label="Trimestre del mapa"
          aria-valuetext={market.published ? formatQuarter(market.period) : 'Sin periodo publicado'}
        />
        <button
          type="button"
          onClick={() => select(periods[index + 1])}
          disabled={!available || !nextPeriod}
          aria-label="Trimestre publicado siguiente"
        >
          ›
        </button>
      </div>
      <ChoiceSelector
        id="timeline-speed"
        label="Velocidad"
        options={SPEEDS}
        value={frameMs}
        onChange={setFrameMs}
        className="timeline-speed"
      />
      {playbackError && (
        <p role="alert">No se pudo preparar {playbackError}. Reproduce de nuevo para reintentar.</p>
      )}
      {loadError && <p>Reintenta los datos de este trimestre para continuar.</p>}
    </div>
  );
}
