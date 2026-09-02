/**
 * DataTable Organism
 * Reusable table component for displaying lists with action buttons
 * Used in MediaManagement, UserManagement, Analytics
 */
export function DataTable({ columns, rows, onRowAction }) {
  return (
    <div className="overflow-x-auto rounded-lg shadow">
      <table className="w-full">
        <thead className="bg-gray-50 border-b">
          <tr>
            {columns.map((col) => (
              <th key={col.key} className="px-6 py-3 text-left text-gray-700 font-semibold">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-6 py-8 text-center text-gray-500">
                No data available
              </td>
            </tr>
          ) : (
            rows.map((row, idx) => (
              <tr key={row.id || idx} className="border-b hover:bg-gray-50">
                {columns.map((col) => (
                  <td key={col.key} className="px-6 py-3 text-gray-700">
                    {col.render ? col.render(row) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
