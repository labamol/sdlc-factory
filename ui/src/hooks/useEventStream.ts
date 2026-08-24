import { useEffect, useState } from "react";
import { FactoryEvent } from "../api/client";

export function useEventStream(projectId: string): FactoryEvent[] {
  const [events, setEvents] = useState<FactoryEvent[]>([]);

  useEffect(() => {
    setEvents([]);
    const source = new EventSource(`/api/v1/stream/projects/${projectId}`);
    source.onmessage = (message) => {
      const event = JSON.parse(message.data) as FactoryEvent;
      setEvents((current) => [...current, event]);
    };
    return () => source.close();
  }, [projectId]);

  return events;
}
