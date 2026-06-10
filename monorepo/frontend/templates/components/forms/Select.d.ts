import * as React from 'react';

export type SelectOption = string | { value: string; label: string };

/** Styled native select with chevron. */
export interface SelectProps {
  label?: string;
  hint?: string;
  value?: string;
  onChange?: (value: string, e: React.ChangeEvent<HTMLSelectElement>) => void;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
  id?: string;
  style?: React.CSSProperties;
}

export function Select(props: SelectProps): JSX.Element;
