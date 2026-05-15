import chatReducer, {
  appendMessages,
  setGeneratingResponse,
} from "./state/slices/chatSlice";

describe("chatSlice", () => {
  it("stores chat messages with typed actions", () => {
    const initialState = chatReducer(undefined, { type: "@@INIT" });
    const loadingState = chatReducer(
      initialState,
      setGeneratingResponse(true)
    );
    const nextState = chatReducer(
      loadingState,
      appendMessages([
        {
          id: "message-1",
          role: "user",
          content: "Hello world",
          date: "2026-04-10T00:00:00.000Z",
        },
      ])
    );

    expect(nextState.generatingResponse).toBe(true);
    expect(nextState.messages).toHaveLength(1);
    expect(nextState.messages[0].content).toBe("Hello world");
  });
});
