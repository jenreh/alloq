import { createElement, useContext } from "react";
import { MantineProvider as MantineCoreProvider } from "@mantine/core";
import { ColorModeContext } from "$/utils/context";

export default function MemoizedMantineProvider({ children, theme, ...props }) {
  const { resolvedColorMode } = useContext(ColorModeContext) || {};
  const mode = resolvedColorMode ?? "light";

  return createElement(
    MantineCoreProvider,
    {
      ...props,
      theme,
      forceColorScheme: mode,
    },
    children
  );
}
