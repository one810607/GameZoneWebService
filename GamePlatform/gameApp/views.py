from django.shortcuts import render,HttpResponse,get_object_or_404,redirect
from .tasks import work_chain
from django.urls import reverse
from django.views import View
from django.contrib.auth import login, logout, authenticate
from .form import *
from django.core.cache import cache
from .cache import get_redis_cache
from .models import User,GamePlatform,GameType,Classification,Game,GamePlatformRelation,GameTypeRelation,Comment,CommentArea,CommentAreaReview
from django.contrib.auth.mixins import LoginRequiredMixin
from .emailverify import send_verify_code
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from .customize import save_message_to_session, icon_rename
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from gameApp.tasks import work_chain
import json


class Signin(View):#宗錡

    def dispatch(self, request, *args, **kwargs):
        self.latest_game = get_redis_cache("latest_game", "latest_game")#皓程
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        if request.user.is_authenticated:
            logout(request)
            return redirect("gameApp:game_list")
        next_url = request.GET.get('next', reverse("gameApp:game_list"))
        return render(request,"signin.html",  {"next": next_url, "latest_games":self.latest_game})

    def post(self, request):
        form = SigninForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username = username, password = password)
            if user is not None:
                login(request, user)
                next_url = request.POST.get('next',reverse("gameApp:game_list"))
                return redirect(next_url)
        errors="Invalid username or password"
        return render(request, 'signin.html', {'form': form, 'errors': errors, 'next': request.POST.get('next', ''), "latest_games":self.latest_game})


class Register(View): #宗錡
    def get(self, request):
        latest_game = get_redis_cache("latest_game", "latest_game")#皓程
        return render(request, "register.html",{"latest_games":latest_game})
    def post(self, request):
        userdata = RegisterForm(request.POST, request.FILES)
        if userdata.is_valid():
            user = userdata.save()
            login(request, user)
            return redirect(reverse("gameApp:game_list"))
        else:
            print(userdata.errors)
            return render(request,'register.html', {"errors": userdata.errors})


class EmailVerify(LoginRequiredMixin, View): #宗錡
    def get(self, request):
        user = request.user
        verify_code = send_verify_code(user.email)
        user.emailverify = verify_code
        user.save()
        return render(request, 'verification_input.html', {"check":1})

    def post(self, request):
        check=1
        user = request.user
        input_code = request.POST["verification_code"]
        if user.emailverify == input_code:
            user.emailverify="已驗證"
            user.save()
            # return redirect("gameApp:user")
            return HttpResponse("""
            <script type="text/javascript">
                setTimeout(function() {
                window.location.href = "/user/";
                }, 5000);  // 5 秒後跳轉
            </script>
            <div class="alert alert-success">
            <p>驗證成功</p>
            <p>5秒後將自動跳轉...</p>
            </div>
            """)
        return render(request, "verification_input.html", locals())


class UserSpace(LoginRequiredMixin, View): #宗錡
    def get(self, request):
        user = request.user
        username = user.username
        icon = user.icon
        phone = user.phone
        gender = user.gender
        birthday = user.birthday
        email = user.email
        emailVerify = user.emailverify
        check = 1
        latest_games = get_redis_cache("latest_game", "latest_game") #皓程
        return render(request, "user.html", locals())

    @method_decorator(csrf_exempt)
    def post(self, request):
        user = User.objects.get(username=request.user)
        if request.FILES.get('icon'):
            post_icon = (request.FILES['icon'])
            path = icon_rename(post_icon, post_icon.name)
            print(default_storage.save(path, post_icon))
            user.icon = path
            user.save()
            return JsonResponse({'success': True, 'url': default_storage.url(user.icon)})
        data = json.loads(request.body)
        field = data.get('field')
        value = data.get('value')
        if field and value:
            setattr(user, field, value)
            user.save()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False})


class Index(View):#宗錡
    def get(self,request):
        ##work_chain()
        if request.user.is_authenticated:
            check = 1
            user = request.user.username,
        games=Game.objects.order_by('-star_count', '?')[:6]
        game_types = get_redis_cache("all_type_objs", "all_type_objs")
        Gid=[game.id for game in games]
        Gname=[game.name for game in games]
        Gimg=[game.picture_game if game.picture_game!='' else "https://fit.univ-angers.fr/wp-content/uploads/sites/2/2019/04/simon-cadoret-picto-photo-noir.png" for game in games]
        latest_games = Game.objects.all().order_by('-release_date')[:16] #皓程
        return render(request, "index.html", locals())

class TrendsGame(View): #皓程
    def get(self,request):
        name = request.GET['name']
        game_type = get_redis_cache("game_type", name)
        all_games = get_redis_cache("all_type_games", game_type)
        latest_game = get_redis_cache("latest_game", "latest_game")
        context = {
            "games_list" : all_games,
            "game_type" : game_type,
            "latest_games" : latest_game
        }
        if request.user.is_authenticated:
            context["check"] = 1
            context["user"] = request.user.username
        return render(request,"list.html",context)
    
    def post(self,request):
        name = request.POST.get('Search', 'Guest')
        all_games = Game.objects.filter(name__contains = name)
        if all_games:
            context = {
                "games_list" : all_games,
                "platform"   : name,
            }
            if request.user.is_authenticated:
                context["check"] = 1
                context["user"] = request.user.username
            return render(request,"list.html",context)
        return HttpResponse("無資料")


class GameDetail(View): #皓程
    def get(self,request,id):
        game = get_redis_cache("game", id)
        latest_game = get_redis_cache("latest_game", "latest_game")
        platform = game.platform.all()
        game_type = game.game_type.all()
        comments = Comment.objects.filter(game = game).order_by('-dt')
        recommand = Game.objects.filter(game_type = game_type[0]).order_by('?')[:12]
        

        if comments.exists():
            star_total = [comment.star_count for comment in comments]
            star_avg = sum(star_total) / len(star_total)
            game.star_count = star_avg
            game.save()
        else:
            star_avg = 0
        
        context={
            "game" : game,
            "platforms" : platform,
            "game_types" : game_type,
            "classification" : game.get_classification_display,
            "release_date" : game.release_date,
            "star" : star_avg,
            "comments" : comments,
            "recommands" : recommand,
            "latest_games" : latest_game,
        }
        if request.user.is_authenticated:
            context["check"] = 1
            context["user"] = request.user.username

        saved_message = request.session.pop('saved_message', '')#宗錡
        saved_score = request.session.pop('saved_score', '')
        if saved_message:
            context['comment'] = saved_message
        if saved_score:
            context['score'] = saved_score

        return render(request,"single.html",context)

    @method_decorator(save_message_to_session)
    def post(self,request,id):
        context = request.POST.get('Message', "")
        score = request.POST.get('score', 1)
        game = get_redis_cache("game", id)
        user = get_redis_cache("user", request.user.username)
        comment = Comment(game = game,user=user,context=context,star_count = float(score))
        comment.save()
        return redirect(reverse("gameApp:game_detail",kwargs={"id" : id}))

class CommentSite(View):#皓程
    def get(self,request):
        latest_games = get_redis_cache("latest_game", "latest_game")
        page = int(request.GET.get('page', 1))
        print(page)
        items_per_page = 5
        comments = CommentArea.objects.all().order_by('-dt')
        paginator = Paginator(comments, items_per_page)
        page_obj = paginator.get_page(page)
        print(page_obj)

        context = {
            "latest_games": latest_games,
            'comments': page_obj,
        }
        saved_message = request.session.pop('saved_message', '')
        if saved_message:
            context['Message'] = saved_message
        if request.user.is_authenticated:
            context["check"] = 1
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            if page > paginator.num_pages:
                context = {
                    "latest_games": latest_games,
                    "comments": [],
                }
            print('ajax')
            return render(request, 'commentlist.html', context)
        else:
            print(paginator.num_pages)
            return render(request, 'comments.html', context)

    @method_decorator(save_message_to_session)
    def post(self,request):
        context = request.POST.get('Message')
        user = get_redis_cache("user", request.user.username)
        CommentArea.objects.create(user = user,context = context)
        return redirect(reverse("gameApp:commentarea"))


class CommentReview(View):#皓程
    def get(self, request, pk):
        latest_games = get_redis_cache("latest_game", "latest_game")
        comment = get_object_or_404(CommentArea, pk = pk)
        comments_review = CommentAreaReview.objects.filter(Comment = comment).order_by('-dt')
        context={
            "latest_games" : latest_games,
            "comment" : comment,
            "comments_review" : comments_review
        }
        saved_message = request.session.pop('saved_message', '')
        if saved_message:
            context['Message'] = saved_message
        if request.user.is_authenticated:
            context["check"] = 1
            context["user"] = request.user.username
        return render(request,"commentsabout.html",context)

    @method_decorator(save_message_to_session)
    def post(self, request, pk):
        context = request.POST.get('Message')
        comment = get_object_or_404(CommentArea, pk = pk)
        user = get_redis_cache("user", request.user.username)
        CommentAreaReview.objects.create(Comment = comment,
                                        user = user,
                                        context = context)
        return redirect(reverse("gameApp:comment_review",kwargs={'pk': pk}))

class Games(View):#皓程
    def get(self,request):
        latest_games = get_redis_cache("latest_game", "latest_game")
        context={
            "latest_games" : latest_games
        }
        
        if request.user.is_authenticated:
            context["check"] = 1
            context["user"] = request.user.username
        return render(request,"games.html",context)


class CommentLike(LoginRequiredMixin, View): #皓程
    def get(self,request,comment_id,game_id):
        user = get_redis_cache("user", request.user.username)
        comment = Comment.objects.get(id = comment_id)
        comment.game_like.add(user)
        comment.save()
        return redirect(reverse("gameApp:game_detail", kwargs={"id" : game_id}))


class CommentAreaLike(LoginRequiredMixin, View): #皓程
    def get(self,request,comment_id):
        user =  get_redis_cache("user", request.user.username)
        comment = get_object_or_404(CommentArea, id = comment_id)
        comment.comment_like.add(user)
        comment.save()
        return redirect(reverse("gameApp:commentarea"))


class CommentAreaReviewLike(LoginRequiredMixin, View): #皓程
    def get(self, request, comment_id, pk):
        user =  get_redis_cache("user", request.user.username)
        comment = get_object_or_404(CommentAreaReview, id = comment_id)
        comment.comment_review_like.add(user)
        comment.save()
        return redirect(reverse("gameApp:comment_review",kwargs={'pk' : pk}))


class ContactUs(View):
    def get(self,request): #皓程
        latest_games = get_redis_cache("latest_game", "latest_game")
        context={
            "latest_games" : latest_games
        }
        
        if request.user.is_authenticated:
            context["check"] = 1
            context["user"] = request.user.username
        saved_message = request.session.pop('saved_message', '')
        saved_subject = request.session.pop('saved_subject', '')
        if saved_message:
            context['Message'] = saved_message
        if saved_subject:
            context["Subject"] = saved_subject
        return render(request,"contact.html", context)

    @method_decorator(save_message_to_session)
    def post(self,request): #崇皓
        user = get_redis_cache("user", request.user.username)
        email =user.email
        subject = request.POST.get('Subject', '')
        message = request.POST.get('Message', '')
        send_mail(subject, message+'\n\n來自 '+email, settings.DEFAULT_FROM_EMAIL, [settings.EMAIL_HOST_USER])
        messages.success(request,"訊息成功寄出")
        return redirect(reverse("gameApp:contact"))
    
