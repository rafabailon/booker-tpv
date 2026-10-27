# User Manual

## Sign-In and Roles

Sign in with the account provided by the administrator. The sidebar shows the areas available to your role. Sign out at the end of a shift, especially on a shared terminal.

- **Cashier:** checkout, catalog lookup, and sales history.
- **Supervisor:** cashier features, inventory, reports, and return/adjustment approval.
- **Administrator:** supervisor features plus account and role management.

## Checkout

1. In `Caja`, search by title/author or scan an ISBN with a reader configured as a keyboard followed by Enter.
2. Select a result to add it to the cart. Adjust quantities in the cart; the displayed stock cannot be exceeded.
3. Select cash or card. For a split tender, choose `Dividir pago` and allocate the full total between the methods. For cash, enter the amount received; change is recorded on the receipt.
4. Select `Cobrar` and wait for confirmation. If a recoverable error appears, the cart is preserved; retrying the same request does not create a duplicate sale.
5. After confirmation, select `Imprimir ticket` for an informational receipt. The sale is saved even if printing fails.

If an item cannot be found, ask an authorized user to verify its ISBN, title, and active status in the catalog.

## Catalog

Search by title, author, or ISBN. Administrators and supervisors can add, edit, and archive books. ISBN is optional, but a supplied value must be valid. Initial book stock is recorded as an auditable movement; use Inventory for later adjustments.

Archiving removes a book from checkout without deleting its history. Catalog price changes do not alter earlier receipts.

## User Accounts (Administrators)

In `Usuarios`, create accounts with a username, an initial password of at least 12 characters, and a role. Administrators can change roles, reset passwords, and activate/deactivate accounts. You cannot deactivate your own account. Inactive accounts lose access immediately; their operation history is retained.

## Returns

A supervisor or administrator opens `Ventas`, selects a ticket, and chooses `Registrar devolución`. Enter a reason, set a return quantity for each line, choose whether each returned item is restocked, and confirm. The interface displays how many units remain returnable. The API rejects quantities above that limit.

The refund is recorded in Booker TPV, but payment is not sent to the external bank terminal. Follow the shop's approved refund policy. Do not restock damaged or unsellable items.

## Inventory and Reports

In `Inventario`, choose a book, enter a positive or negative quantity change, and provide a verifiable reason. The system rejects changes that would make stock negative. `Informes` shows daily net sales, gross sales, refunds, and books at or below the displayed low-stock threshold. Returns are attributed to the day they are recorded.

## Troubleshooting

- **Connection/API error:** do not initiate another external payment until you know whether the sale was recorded. Check `Ventas` first.
- **Stock conflict:** verify the current stock and update the cart.
- **Expired session:** sign in again.
- **Print failure:** retrieve the saved ticket from `Ventas`; printing is separate from saving a sale.
