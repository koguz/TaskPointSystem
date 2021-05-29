$(function($) {
    $('.content-text').each(function(index, value) {
      $(this).html($(this).html().substring(0,150));
    });

    $('#sidebar-collapse').click(function () {
        $('#sidebar').toggleClass('sidebar-active');
        $('.main-screen').toggleClass('main-screen-active');
    });

    $('#task-more-details-button').click(function () {
       $('.task-additional-details').slideToggle();
       $('.task-history').slideUp();
    });

    $('#task-history-button').click(function () {
       $('.task-history').slideToggle();
       $('.task-additional-details').slideUp();
    });

    addListenersToTeamMemberAccordions();
});

function addListenersToTeamMemberAccordions() {
    const acc = document.getElementsByClassName("accordion");
    let i;

    for (i = 0; i < acc.length; i++) {
      acc[i].addEventListener("click", function() {
        this.classList.toggle("active");
          let task_list = this.nextElementSibling;
          for (let task_index = 0; task_index < task_list.children.length; task_index++) {
            let task = task_list.children.item(task_index);
            if (task.style.display === "block") {
                task.style.display = "none";
            } else {
                task.style.display = "block";
            }
          }
      });
    }
}