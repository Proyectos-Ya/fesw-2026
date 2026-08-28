import * as React from 'react';

/** Avatar with image or auto initials. Circle for people, square for companies. */
export interface AvatarProps {
  name?: string;
  src?: string;
  size?: 'xs' | 'sm' | 'md' | 'lg';
  /** "circle" for people, "square" (rounded) for companies. */
  shape?: 'circle' | 'square';
  style?: React.CSSProperties;
}

export function Avatar(props: AvatarProps): JSX.Element;
