import * as React from 'react';

/** Lucide icon wrapper. Requires the Lucide UMD script on the page. */
export interface IconProps {
  /** Lucide icon name, e.g. "search", "sparkles", "check". */
  name: string;
  size?: number;
  strokeWidth?: number;
  color?: string;
  style?: React.CSSProperties;
}

export function Icon(props: IconProps): JSX.Element;
