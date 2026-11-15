import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Navbar } from "./Navbar";

describe("responsive navigation controls", () => {
  it("opens the compact menu and navigates to a section", () => {
    render(<Navbar />);
    const toggle = screen.getByRole("button", { name: "Open menu" });
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const menu = screen.getByRole("navigation", { name: "Expanded navigation" });
    fireEvent.click(within(menu).getByRole("link", { name: "Landing sites" }));
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });
});
