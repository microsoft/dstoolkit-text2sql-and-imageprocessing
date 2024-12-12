using Microsoft.AspNetCore.Mvc;

namespace ExcelToSQL.UI.Controllers
{
    public class QueryController : Controller
    {
        public IActionResult Index()
        {
            return View();
        }
    }
}
