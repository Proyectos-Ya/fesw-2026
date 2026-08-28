import * as React from 'react';

export type TabItem = string | { value: string; label: string; count?: number; icon?: React.ReactNode };

/** Underline tab bar (controlled). */
export interface TabsProps {
  tabs: TabItem[];
  value?: string;
  onChange?: (value: string) => void;
  style?: React.CSSProperties;
}

export function Tabs(props: TabsProps): JSX.Element;
