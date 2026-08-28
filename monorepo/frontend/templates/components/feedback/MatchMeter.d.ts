import * as React from 'react';

/**
 * Signature ProyectosYa component: a circular gauge showing the AI-computed
 * compatibility between a company and a tender (0–100). Colour shifts by
 * threshold — teal ≥80, amber ≥60, muted below.
 *
 * @startingPoint section="Feedback" subtitle="Compatibility score gauge — the brand's signature metric" viewport="700x150"
 */
export interface MatchMeterProps {
  /** Score 0–100. */
  value: number;
  size?: 'sm' | 'md' | 'lg';
  /** Optional qualitative label shown beside the ring (e.g. "Alta", "Media"). */
  label?: string;
  /** Show the numeric % in the centre. Default true. */
  showValue?: boolean;
  style?: React.CSSProperties;
}

export function MatchMeter(props: MatchMeterProps): JSX.Element;
