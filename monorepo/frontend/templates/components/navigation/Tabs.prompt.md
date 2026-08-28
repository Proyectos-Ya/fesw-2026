Underline tab bar with teal indicator. Controlled via `value` / `onChange`.

```jsx
<Tabs value={tab} onChange={setTab}
  tabs={[{value:'match',label:'Para ti',count:8},{value:'todas',label:'Todas'}]} />
```

Items accept strings or `{value,label,count,icon}`.
