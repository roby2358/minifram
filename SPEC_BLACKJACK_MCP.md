# Blackjack MCP - Technical Specification

A Model Context Protocol server implementing simplified blackjack for testing multi-round tool interactions.

## Purpose

Provide a stateful game MCP server to verify that LLMs can correctly handle multi-turn interactions with tools, maintain game state across calls, and respond appropriately to dynamic game outcomes.

## Functional Requirements

### Session Management

- The server MUST maintain a single game session per client connection
- The session MUST store the dealer's hand and the player's hand
- The server MUST reset the session when `blackjack_deal` is called

### Card Generation

- The server MUST generate cards uniformly at random from: 2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K, A
- Face cards (J, Q, K) MUST count as 10
- Aces MUST count as either 1 or 11, whichever produces the best hand value without busting
- The server MUST NOT maintain a deck (each draw is independent)
- The server MUST NOT represent card suits

### Game Tools

The server MUST provide three tools via MCP `tools/list`:

#### blackjack_deal

- The server MUST start a new hand
- The server MUST deal two cards to the dealer with the first card face-down (hidden)
- The server MUST deal two cards to the player face-up (visible)
- If the player has exactly 21, the server MUST declare "Player wins!" and end the hand
- If the dealer has exactly 21 after revealing both cards, the server MUST declare "Dealer wins!" and end the hand
- The server MUST return the current game state

#### blackjack_hit

- The server MUST deal one additional card to the player
- If the player's hand total exceeds 21, the server MUST declare "Bust! Dealer wins!" and end the hand
- If the player's hand total is 21 or less, the server MUST return the updated game state
- The server MUST allow multiple sequential calls to `blackjack_hit`

#### blackjack_stand

- The server MUST reveal the dealer's hidden card
- The dealer MUST draw cards until reaching 17 or higher
- If the dealer busts (exceeds 21), the server MUST declare "Player wins!" and end the hand
- If the dealer's hand total equals the player's hand total, the server MUST declare "Push! Dealer wins!" and end the hand
- If the dealer's hand total exceeds the player's hand total without busting, the server MUST declare "Dealer wins!" and end the hand
- If the player's hand total exceeds the dealer's hand total, the server MUST declare "Player wins!" and end the hand

### Response Format

All tool calls MUST return a string in the following format:

```
Dealer: <cards>
Player: <cards>
<optional message>
```

- Hidden dealer cards MUST be represented as `X`
- Visible cards MUST be represented by their value (2-10, J, Q, K, A)
- Cards MUST be space-separated
- Optional messages MUST appear on a new line after the hand display

Valid messages:
- `Player wins!` - Player has better hand or dealer busts
- `Dealer wins!` - Dealer has better hand
- `Bust! Dealer wins!` - Player exceeds 21
- `Push! Dealer wins!` - Hands tie (dealer wins ties)

## Non-Functional Requirements

### Protocol Compliance

- The server MUST implement MCP via stdio (standard input/output)
- The server MUST respond to JSON-RPC 2.0 requests
- The server MUST support `initialize`, `tools/list`, and `tools/call` methods

### Game Simplifications

- The server MUST NOT implement betting
- The server MUST NOT implement splits, doubles, or insurance
- The server MUST NOT enforce a maximum number of cards per hand
- The server MUST treat pushes as dealer wins

## Implementation Notes

### Ace Valuation

Aces are automatically valued optimally. When calculating hand totals, the server tries counting aces as 11 first, then as 1 if that would prevent a bust. This maximizes the player's chances without requiring explicit choice.

### Dealer Behavior

The dealer follows standard casino rules: draw until reaching 17 or higher, then stop. The dealer reveals the hidden card only when the player calls `blackjack_stand`.

### State Persistence

Game state exists only during the MCP server process lifetime. Terminating the server resets all game state. Each `blackjack_deal` call starts a fresh hand but maintains the same session.

### Random Number Generation

Cards are generated using uniform random distribution without replacement tracking. This simplifies implementation and is sufficient for testing multi-round tool interactions.