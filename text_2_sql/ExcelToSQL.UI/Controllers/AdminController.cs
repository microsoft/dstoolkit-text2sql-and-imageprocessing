using Microsoft.AspNetCore.Mvc;

namespace ExcelToSQL.UI.Controllers
{
    public class AdminController : Controller
    {
        public IActionResult UploadData()
        {
            return View();
        }
    }
}
