## 2024-05-24 - Memoizing Markdown Parsing in React Stream Updates
**Learning:** During streaming, state rapidly updates the `messages` array, causing all messages to re-render. Executing expensive regex-based markdown parsing inside the map function leads to significant performance bottlenecks and stuttering.
**Action:** Always extract expensive string manipulations (like regex matching) from inside rendering loops into separate components wrapped with `React.memo` to prevent unnecessary re-computations when parent states change rapidly.
