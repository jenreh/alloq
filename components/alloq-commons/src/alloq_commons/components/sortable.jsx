import React, { createContext, useContext, useEffect, useState } from "react";
import { DragDropContext, Draggable, Droppable } from "@hello-pangea/dnd";

// The order shown while the server confirms a move, so a dropped row does not
// jump back for a moment. Items apply it as CSS ``order``.
const PendingOrder = createContext(null);

export function SortableList({
  ids = [],
  version = 0,
  droppableId = "sortable",
  instructions,
  onReorder,
  className,
  children,
}) {
  const [pending, setPending] = useState(null);
  const signature = ids.join("\u0000");
  // The stored order or the answer to a move ends the interim order.
  useEffect(() => setPending(null), [signature, version]);

  const onDragEnd = (result) => {
    const { draggableId, source, destination } = result;
    if (!destination || destination.index === source.index) {
      return;
    }
    const next = (pending || ids).filter((id) => id !== draggableId);
    next.splice(destination.index, 0, draggableId);
    setPending(next);
    if (onReorder) {
      onReorder(draggableId, destination.index);
    }
  };

  return (
    <DragDropContext onDragEnd={onDragEnd} dragHandleUsageInstructions={instructions}>
      <Droppable droppableId={droppableId}>
        {(drop) => (
          <div
            ref={drop.innerRef}
            {...drop.droppableProps}
            className={className}
            style={{ display: "flex", flexDirection: "column" }}
          >
            <PendingOrder.Provider value={pending}>{children}</PendingOrder.Provider>
            {drop.placeholder}
          </div>
        )}
      </Droppable>
    </DragDropContext>
  );
}

export function SortableItem({ itemId, index, disabled = false, className, children }) {
  const pending = useContext(PendingOrder);
  const order = pending ? pending.indexOf(itemId) : undefined;
  return (
    <Draggable draggableId={itemId} index={index} isDragDisabled={disabled}>
      {(drag, snapshot) => (
        <div
          ref={drag.innerRef}
          {...drag.draggableProps}
          {...drag.dragHandleProps}
          className={className}
          data-dragging={snapshot.isDragging ? "true" : undefined}
          style={{ ...drag.draggableProps.style, order }}
          onKeyDown={(event) => {
            // Enter opens the row like a click; space stays for dragging.
            if (event.key === "Enter" && event.target === event.currentTarget) {
              event.currentTarget.firstElementChild?.click();
            }
          }}
        >
          {children}
        </div>
      )}
    </Draggable>
  );
}
