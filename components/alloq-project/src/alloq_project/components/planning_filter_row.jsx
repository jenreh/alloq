import React, { useEffect, useRef, useState } from "react";
import { ActionIcon, Box, OverflowList, Popover, Stack } from "@mantine/core";

function OverflowFilters({ items }) {
  const [opened, setOpened] = useState(false);
  const closeTimer = useRef(null);
  const dropdown = useRef(null);
  const target = useRef(null);

  useEffect(() => () => clearTimeout(closeTimer.current), []);

  const open = () => {
    clearTimeout(closeTimer.current);
    setOpened(true);
  };
  const close = () => {
    clearTimeout(closeTimer.current);
    setOpened(false);
  };
  const closeAfterLeave = () => {
    clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => {
      if (!dropdown.current?.contains(document.activeElement) &&
          document.activeElement !== target.current) {
        setOpened(false);
      }
    }, 180);
  };

  return (
    <Popover
      opened={opened}
      onDismiss={close}
      position="bottom-end"
      withArrow
      shadow="md"
      radius="md"
      width="max-content"
    >
      <Popover.Target>
        <ActionIcon
          ref={target}
          aria-label="Weitere Filter"
          variant="subtle"
          color="alloqTeal.5"
          size="lg"
          radius="md"
          onMouseEnter={open}
          onMouseLeave={closeAfterLeave}
          onBlur={closeAfterLeave}
          onClick={open}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              close();
            }
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" strokeWidth="2" strokeLinecap="round"
               strokeLinejoin="round" aria-hidden="true">
            <path d="m6 9 6 6 6-6" />
          </svg>
        </ActionIcon>
      </Popover.Target>
      <Popover.Dropdown
        ref={dropdown}
        className="alloq-planning-overflow"
        aria-label="Weitere Planungsfilter"
        maw="calc(100vw - 2rem)"
        onMouseEnter={open}
        onMouseLeave={closeAfterLeave}
        onFocusCapture={open}
        onBlurCapture={closeAfterLeave}
      >
        <Stack gap="md" align="flex-start">
          {items.map((item) => (
            <Box key={item.key} maw="100%">
              {item}
            </Box>
          ))}
        </Stack>
      </Popover.Dropdown>
    </Popover>
  );
}

export function PlanningFilterRow({ children }) {
  // A stable row height prevents resize loops during overflow measurement.
  return (
    <OverflowList
      data={React.Children.toArray(children)}
      gap="md"
      maxRows={1}
      w="100%"
      pb="md"
      h="calc(2.25rem + var(--mantine-spacing-md))"
      className="alloq-planning-filters"
      style={{ minWidth: 0, alignItems: "stretch", alignContent: "flex-start" }}
      renderItem={(item) => (
        <Box w="max-content" style={{ flexShrink: 0, display: "flex", alignItems: "center" }}>
          {item}
        </Box>
      )}
      renderOverflow={(items) => (
        <Box style={{ flexShrink: 0, display: "flex", alignItems: "center" }}>
          <OverflowFilters items={items} />
        </Box>
      )}
    />
  );
}
