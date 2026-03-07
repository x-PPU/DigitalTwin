
% k = table(a,x',b,t_1',t','VariableNames',{'a_acc','dot_phi', 'a_de','M_1 Time','M_2 Time'});
% xlswrite('sample.xls', [a',x',b',t_1',t_2']);

% figure(1);
% plot(1:10000,Z(1:10000,1),1:10000,Z(1:10000,2),'--');
% legend('low-fidelity(M1)','high-fidelity(M2)')
% xlabel('Rank Index of solutions based on simple model');
% ylabel('Total Production Time');

% figure(5);
% plot(x_3,t_3,x_3,t_4);
% xlabel('dot_ phi [rad/s]');
% ylabel('t [s]'); 
% legend('t_1','t_2')
% for i=1:length(x_3)
% text(x_3(i),t_3(i),num2str(t_3(i)));
% text(x_3(i),t_4(i),num2str(t_4(i)));
% end
% A=xlsread('sample_rising.xls');
% formatSpec = '(%.1f,%.2f,%d)';
% B=strings(20,1);
% for i=1:20
%   B(i,1)=sprintf(formatSpec,A(i,1),A(i,2),A(i,3));
% end
% 
% 
% figure(2);
% plot(1:20,Z(1:20,2),'-x');
% set(gca,'XTick',1:20);
% set(gca,'XTickLabel',B(1:20,1));
% set(gca,'XTickLabelRotation',90)
% for i=1:20
%   text(i,Z(i,2),char(B(i,1)));
% end
% xlabel('Control Parameter Alternatives');
% ylabel('Total Production Time');

C=xlsread('sample.xls');

formatSpec = '(%.1f,%.2f,%.1f)';
B=strings(41,1);
B(1,1)=sprintf(formatSpec,C(1,1),C(1,2),C(1,3));
for i=2:41
  B(i,1)=sprintf(formatSpec,C((i-1)*250,1),C((i-1)*250,2),C((i-1)*250,3));
end
figure(3);
plot(1:10000,C(1:10000,5));
xlabel('Rank Index of solutions based on complex model');
ylabel('Total Production Time');
set(gca,'XTick',1:250:10000);
set(gca,'XTickLabel',B(1:41,1));
set(gca,'XTickLabelRotation',90)
% for i=1:40
%   text(i*250,Z(i*250,2),char(B(i,1)));
% end