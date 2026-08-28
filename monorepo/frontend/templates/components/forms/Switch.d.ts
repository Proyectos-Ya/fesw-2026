import * as React from 'react';

/** Toggle switch with optional inline label. */
export interface SwitchProps {
  checked?: boolean;
  onChange?: (checked: boolean, e: React.ChangeEvent<HTMLInputElement>) => void;
  label?: React.ReactNode;
  disabled?: boolean;
  id?: string;
  style?: React.CSSProperties;
}

export function Switch(props: SwitchProps): JSX.Element;
